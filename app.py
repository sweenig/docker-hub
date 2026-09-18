from flask import Flask, render_template, request
import subprocess
import json
import re
import os
from datetime import datetime
from flask import request, jsonify

app = Flask(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'services.json')
SERVICE_CONFIG_PATH = os.getenv('SERVICE_CONFIG_PATH', DEFAULT_CONFIG_PATH)


def normalize_root_path(root_path):
    """Normalize an optional service root path for URL joining."""
    if root_path is None:
        return ''

    normalized = str(root_path).strip()
    if not normalized:
        return ''

    return '/' + normalized.lstrip('/')


def normalize_use_ssl(use_ssl):
    """Normalize persisted use_ssl values to a strict boolean."""
    if isinstance(use_ssl, bool):
        return use_ssl

    if isinstance(use_ssl, (int, float)):
        return bool(use_ssl)

    if isinstance(use_ssl, str):
        return use_ssl.strip().lower() in ('1', 'true', 'yes', 'on')

    return False


def build_service_url(base_url, use_ssl, root_path):
    """Build final service URL with optional protocol override and root path."""
    resolved_url = base_url
    if use_ssl:
        if base_url.startswith('//'):
            resolved_url = f"https:{base_url}"
        elif base_url.startswith('http://'):
            resolved_url = f"https://{base_url[len('http://'):] }"

    return f"{resolved_url}{root_path}"


def normalize_port_range(start, end):
    """Normalize and validate a configured port range."""
    if start is None or end is None:
        return (None, None)

    try:
        start_int = int(start)
        end_int = int(end)
    except (TypeError, ValueError):
        return (None, None)

    if start_int < 1 or end_int > 65535 or start_int > end_int:
        return (None, None)

    return (start_int, end_int)


def find_first_available_port(range_start, range_end, used_ports):
    """Return the first port in range that is not used, otherwise None."""
    if range_start is None or range_end is None:
        return None

    for port in range(range_start, range_end + 1):
        if port not in used_ports:
            return port

    return None


def normalize_manual_ports(ports):
    """Normalize a user-supplied ports override to a sorted list of valid ints."""
    if not isinstance(ports, list):
        return []

    normalized = set()
    for port in ports:
        try:
            port_int = int(port)
        except (TypeError, ValueError):
            continue
        if 1 <= port_int <= 65535:
            normalized.add(port_int)

    return sorted(normalized)


def get_exposed_ports(container_id):
    """Return declared TCP EXPOSE ports for a container.

    docker ps reports no port mappings for host-network containers (there's no
    publish/NAT rule to show), so this falls back to the image's declared
    EXPOSE ports to guess what the container is actually listening on.
    """
    try:
        result = subprocess.run(
            ['docker', 'inspect', container_id, '--format', '{{json .Config.ExposedPorts}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []

        ports_map = json.loads(result.stdout.strip() or 'null') or {}
        ports = set()
        for key in ports_map:
            proto_port = key.split('/', 1)
            if len(proto_port) == 2 and proto_port[1] == 'tcp' and proto_port[0].isdigit():
                ports.add(int(proto_port[0]))

        return sorted(ports)
    except Exception as e:
        print(f"Error inspecting exposed ports for {container_id}: {e}")
        return []


def _default_service_config():
    return {
        "categories": {
            "Other": {
                "icon": "🐳",
                "name": "Other"
            }
        },
        "services": {},
        "defaults": {
            "name": "Docker service",
            "description": "Docker service",
            "icon": "🐳",
            "category": "Other"
        }
    }

# Add custom Jinja2 filter for contains test
@app.template_filter('contains')
def contains_filter(value, substring):
    return substring in str(value)

def get_docker_containers():
    """Get running Docker containers and their port mappings"""
    try:
        # Run docker ps command to get container information
        result = subprocess.run(
            ['docker', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"Docker command failed: {result.stderr}")
            return []
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    container_info = json.loads(line)
                    containers.append(container_info)
                except json.JSONDecodeError:
                    continue
        
        print(f"Found {len(containers)} containers")
        for container in containers:
            print(f"Container: {container.get('Names', 'Unknown')} - Ports: {container.get('Ports', 'None')}")
        
        return containers
    except Exception as e:
        print(f"Error getting Docker containers: {e}")
        return []

def extract_ports(ports_str):
    """Extract port mappings from docker ps output"""
    if not ports_str:
        return []
    
    ports = []
    # Parse port mappings like "0.0.0.0:8080->8080/tcp, 0.0.0.0:3001->80/tcp"
    port_pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)->(\d+)/tcp'
    matches = re.findall(port_pattern, ports_str)
    
    for match in matches:
        host_ip, host_port, container_port = match
        ports.append({
            'host_port': host_port,
            'container_port': container_port,
            'url': f"//{request.host.split(':')[0]}:{host_port}"
        })
    
    return ports

def load_service_config():
    """Load service configuration from JSON file"""
    try:
        with open(SERVICE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Warning: {SERVICE_CONFIG_PATH} not found, initializing configuration")

        # If writing to an external volume path, seed it from the image's default config.
        if SERVICE_CONFIG_PATH != DEFAULT_CONFIG_PATH and os.path.exists(DEFAULT_CONFIG_PATH):
            try:
                with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    seeded_config = json.load(f)
                save_service_config(seeded_config)
                return seeded_config
            except json.JSONDecodeError:
                print(f"Warning: bundled default config at {DEFAULT_CONFIG_PATH} is invalid JSON")

        fallback_config = _default_service_config()
        save_service_config(fallback_config)
        return fallback_config
    except json.JSONDecodeError as e:
        print(f"Error parsing {SERVICE_CONFIG_PATH}: {e}")
        fallback_config = _default_service_config()
        save_service_config(fallback_config)
        return fallback_config

def save_service_config(config):
    """Save service configuration to JSON file"""
    config_dir = os.path.dirname(SERVICE_CONFIG_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(SERVICE_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# --- API endpoints for CRUD ---
@app.route('/api/services', methods=['GET'])
def api_get_services():
    config = load_service_config()
    return jsonify(config)

@app.route('/api/services', methods=['POST'])
def api_add_service():
    config = load_service_config()
    data = request.json
    data = data or {}
    display_name = data.get('name')
    if not display_name:
        return jsonify({'error': 'Service name required'}), 400
    # Allow client to supply an explicit key (container name) while keeping 'name' as the display name
    key = data.get('key') or display_name
    # Copy data to store and remove 'key' to avoid persisting it
    data_to_store = data.copy()
    if 'key' in data_to_store:
        del data_to_store['key']
    data_to_store['root_path'] = normalize_root_path(data_to_store.get('root_path'))
    data_to_store['use_ssl'] = normalize_use_ssl(data_to_store.get('use_ssl'))
    config['services'][key] = data_to_store
    save_service_config(config)
    return jsonify({'success': True, 'service': data_to_store, 'key': key})

@app.route('/api/services/<name>', methods=['PUT'])
def api_update_service(name):
    config = load_service_config()
    data = request.json or {}
    if name not in config['services']:
        return jsonify({'error': 'Service not found'}), 404
    data['root_path'] = normalize_root_path(data.get('root_path'))
    data['use_ssl'] = normalize_use_ssl(data.get('use_ssl'))
    config['services'][name] = data
    save_service_config(config)
    return jsonify({'success': True, 'service': data})

@app.route('/api/services/<name>', methods=['DELETE'])
def api_delete_service(name):
    config = load_service_config()
    if name not in config['services']:
        return jsonify({'error': 'Service not found'}), 404
    del config['services'][name]
    save_service_config(config)
    return jsonify({'success': True})

@app.route('/api/categories', methods=['GET'])
def api_get_categories():
    config = load_service_config()
    return jsonify(config.get('categories', {}))

@app.route('/api/categories', methods=['POST'])
def api_add_category():
    config = load_service_config()
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Category name required'}), 400
    config['categories'][name] = data
    save_service_config(config)
    return jsonify({'success': True, 'category': data})

@app.route('/api/categories/<name>', methods=['PUT'])
def api_update_category(name):
    config = load_service_config()
    data = request.json
    if name not in config['categories']:
        return jsonify({'error': 'Category not found'}), 404
    config['categories'][name] = data
    save_service_config(config)
    return jsonify({'success': True, 'category': data})

@app.route('/api/categories/<name>', methods=['DELETE'])
def api_delete_category(name):
    config = load_service_config()
    if name not in config['categories']:
        return jsonify({'error': 'Category not found'}), 404
    del config['categories'][name]
    # If there is an order list, remove the deleted category from it
    if 'categoryOrder' in config and isinstance(config['categoryOrder'], list):
        config['categoryOrder'] = [c for c in config['categoryOrder'] if c != name]
    save_service_config(config)
    return jsonify({'success': True})

# Endpoint to update category order
@app.route('/api/categories/order', methods=['PUT'])
def api_update_category_order():
    config = load_service_config()
    data = request.json or {}
    order = data.get('order', [])
    if not isinstance(order, list):
        return jsonify({'error': 'Order must be a list of category names'}), 400
    # Persist order as provided; unknown names are allowed but will be ignored when rendering
    config['categoryOrder'] = order
    save_service_config(config)
    return jsonify({'success': True, 'order': order})


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    config = load_service_config()
    settings = config.get('settings', {})
    excluded = config.get('excludedServices', [])
    # Normalize excluded to list of strings
    excluded = excluded if isinstance(excluded, list) else []
    return jsonify({'settings': settings, 'excludedServices': excluded})


@app.route('/api/settings', methods=['PUT'])
def api_update_settings():
    config = load_service_config()
    data = request.json or {}
    settings = config.get('settings', {})
    # Update appTitle if provided
    if 'appTitle' in data:
        settings['appTitle'] = data.get('appTitle')
    if 'portRangeStart' in data or 'portRangeEnd' in data:
        current_start = settings.get('portRangeStart')
        current_end = settings.get('portRangeEnd')
        requested_start = data.get('portRangeStart', current_start)
        requested_end = data.get('portRangeEnd', current_end)
        normalized_start, normalized_end = normalize_port_range(requested_start, requested_end)
        if normalized_start is None or normalized_end is None:
            return jsonify({'error': 'Invalid port range. Use values between 1 and 65535 with start <= end.'}), 400
        settings['portRangeStart'] = normalized_start
        settings['portRangeEnd'] = normalized_end
    config['settings'] = settings
    save_service_config(config)
    return jsonify({'success': True, 'settings': settings})


@app.route('/api/settings/exclude', methods=['POST'])
def api_add_excluded_service():
    config = load_service_config()
    data = request.json or {}
    name = data.get('name')
    # Allow client to supply key+port instead of pre-formatted name
    if not name:
        key = data.get('key')
        port = data.get('port')
        if key and port:
            name = f"{key}:{port}"
    if not name:
        return jsonify({'error': 'Name (or key+port) required'}), 400
    excluded = config.get('excludedServices', [])
    if not isinstance(excluded, list):
        excluded = []
    if name not in excluded:
        excluded.append(name)
    config['excludedServices'] = excluded
    save_service_config(config)
    return jsonify({'success': True, 'excludedServices': excluded})


@app.route('/api/settings/exclude/<name>', methods=['DELETE'])
def api_remove_excluded_service(name):
    config = load_service_config()
    excluded = config.get('excludedServices', [])
    if not isinstance(excluded, list):
        excluded = []
    if name in excluded:
        excluded = [n for n in excluded if n != name]
    config['excludedServices'] = excluded
    save_service_config(config)
    return jsonify({'success': True, 'excludedServices': excluded})

def get_service_info(container_name):
    """Get additional service information based on container name"""
    config = load_service_config()
    services = config.get('services', {})
    # If not found, return a special marker for uncategorized
    if container_name in services:
        service_info = services[container_name].copy()
        service_info['root_path'] = normalize_root_path(service_info.get('root_path'))
        service_info['use_ssl'] = normalize_use_ssl(service_info.get('use_ssl'))
        return service_info
    else:
        return {
            'name': container_name,
            'description': 'Categorize this service in settings',
            'icon': '🐳',
            'category': 'Other',
            'root_path': '',
            'use_ssl': False,
            'uncategorized': True
        }

@app.route('/')
def index():
    containers = get_docker_containers()
    services = []
    used_ports = set()
    
    print(f"Processing {len(containers)} containers")
    
    for container in containers:
        container_name = container.get('Names', '').replace('/', '')
        ports = extract_ports(container.get('Ports', ''))
        is_host_network = container.get('Networks') == 'host'

        print(f"Container: {container_name}, Ports: {ports}")

        if not ports and not is_host_network:
            continue

        service_info = get_service_info(container_name)

        if not ports and is_host_network:
            # docker ps has no port mapping to report for host-network containers,
            # since they bind directly to the host's interfaces with no publish/NAT
            # rule. Fall back to a manual override, then the image's declared EXPOSE
            # ports, so these containers aren't silently dropped from the dashboard.
            manual_ports = normalize_manual_ports(service_info.get('ports'))
            candidate_ports = manual_ports or get_exposed_ports(container.get('ID', container_name))
            host = request.host.split(':')[0]
            if candidate_ports:
                ports = [
                    {'host_port': str(port), 'container_port': str(port), 'url': f"//{host}:{port}"}
                    for port in candidate_ports
                ]
            else:
                ports = [{'host_port': None, 'container_port': None, 'url': None}]

        for port_info in ports:
            if port_info['host_port'] is not None:
                try:
                    used_ports.add(int(port_info['host_port']))
                except (TypeError, ValueError):
                    pass

            service_data = {
                'name': service_info['name'],
                'container_name': container_name,
                'description': service_info['description'],
                'icon': service_info['icon'],
                'category': service_info['category'],
                'root_path': service_info.get('root_path', ''),
                'use_ssl': service_info.get('use_ssl', False),
                'url': build_service_url(
                    port_info['url'],
                    service_info.get('use_ssl', False),
                    service_info.get('root_path', '')
                ) if port_info['url'] else None,
                'host_port': port_info['host_port'],
                'container_port': port_info['container_port'],
                'status': container.get('Status', 'Unknown'),
                'created': container.get('CreatedAt', 'Unknown'),
                'host_network': is_host_network
            }
            services.append(service_data)
            print(f"Added service: {service_data['name']} at {service_data['url']}")
    
    print(f"Total services found: {len(services)}")
    
    # Group services by category
    categories = {}
    for service in services:
        category = service['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(service)
    

    # Load persisted config early so settings like excluded services and appTitle are available
    config = load_service_config()

    # Parse EXCLUDED_SERVICES from env and from persisted config (list of names or name:port)
    excluded_services_raw = []
    env_excluded = os.environ.get('EXCLUDED_SERVICES', '')
    if env_excluded:
        excluded_services_raw.extend([name.strip() for name in env_excluded.split(',') if name.strip()])
    cfg_excluded = config.get('excludedServices', [])
    if isinstance(cfg_excluded, list):
        excluded_services_raw.extend([name for name in cfg_excluded if isinstance(name, str) and name.strip()])
    excluded_containers = set()
    excluded_container_ports = set()
    for item in excluded_services_raw:
        if ':' in item:
            cname, port = item.split(':', 1)
            excluded_container_ports.add((cname.strip(), port.strip()))
        else:
            excluded_containers.add(item)

    # Separate main services from excluded services (by port or container)
    main_services = []
    other_services = []
    for service in services:
        cname = service['container_name']
        hport = str(service.get('host_port', ''))
        if service.get('host_port') is None:
            # No port could be detected (host-network container with no manual
            # override or EXPOSE metadata) - surface it under Other Services
            # instead of a normal category, since there's no port to link to.
            other_services.append(service)
        elif (cname, hport) in excluded_container_ports:
            other_services.append(service)
        elif cname in excluded_containers:
            other_services.append(service)
        else:
            main_services.append(service)
    
    # Group main services by category
    categories = {}
    for service in main_services:
        category = service['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(service)
    
    # Load category configuration
    category_config = config.get('categories', {})
    # Determine category display order based on persisted order
    configured_order = config.get('categoryOrder', [])
    # Final order: configured order, followed by any categories not listed yet
    present_categories = list(categories.keys())
    category_order = [c for c in configured_order if c in present_categories]
    for c in present_categories:
        if c not in category_order:
            category_order.append(c)
    
    # Determine app title: env var overrides persisted setting
    app_title = os.environ.get('APPTITLE') or config.get('settings', {}).get('appTitle') or 'Docker Services Hub'
    settings = config.get('settings', {})
    configured_start, configured_end = normalize_port_range(
        settings.get('portRangeStart'),
        settings.get('portRangeEnd')
    )
    first_available_port = find_first_available_port(configured_start, configured_end, used_ports)

    return render_template(
        'index.html',
        categories=categories,
        services=main_services,
        containers=containers,
        app_title=app_title,
        other_services=other_services,
        category_config=category_config,
        category_order=category_order,
        first_available_port=first_available_port,
        configured_port_range_start=configured_start,
        configured_port_range_end=configured_end
    )

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

@app.route('/debug')
def debug():
    """Debug endpoint to see container information"""
    containers = get_docker_containers()
    return {
        'containers': containers,
        'total_containers': len(containers),
        'timestamp': datetime.now().isoformat()
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

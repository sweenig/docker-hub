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
    config['services'][key] = data_to_store
    save_service_config(config)
    return jsonify({'success': True, 'service': data_to_store, 'key': key})

@app.route('/api/services/<name>', methods=['PUT'])
def api_update_service(name):
    config = load_service_config()
    data = request.json
    if name not in config['services']:
        return jsonify({'error': 'Service not found'}), 404
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
        return services[container_name]
    else:
        return {
            'name': container_name,
            'description': 'Categorize this service in settings',
            'icon': '🐳',
            'category': 'Other',
            'uncategorized': True
        }

@app.route('/')
def index():
    containers = get_docker_containers()
    services = []
    
    print(f"Processing {len(containers)} containers")
    
    for container in containers:
        container_name = container.get('Names', '').replace('/', '')
        ports = extract_ports(container.get('Ports', ''))
        
        print(f"Container: {container_name}, Ports: {ports}")
        
        if ports:  # Only include containers with exposed ports
            service_info = get_service_info(container_name)
            
            for port_info in ports:
                service_data = {
                    'name': service_info['name'],
                    'container_name': container_name,
                    'description': service_info['description'],
                    'icon': service_info['icon'],
                    'category': service_info['category'],
                    'url': port_info['url'],
                    'host_port': port_info['host_port'],
                    'container_port': port_info['container_port'],
                    'status': container.get('Status', 'Unknown'),
                    'created': container.get('CreatedAt', 'Unknown')
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
        if (cname, hport) in excluded_container_ports:
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
    return render_template(
        'index.html',
        categories=categories,
        services=main_services,
        containers=containers,
        app_title=app_title,
        other_services=other_services,
        category_config=category_config,
        category_order=category_order
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

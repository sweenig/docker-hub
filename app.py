from flask import Flask, render_template, request
import subprocess
import json
import re
import os
from datetime import datetime
from flask import request, jsonify

app = Flask(__name__)

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
        with open('services.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("Warning: services.json not found, using default configuration")
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
    except json.JSONDecodeError as e:
        print(f"Error parsing services.json: {e}")
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

def save_service_config(config):
    """Save service configuration to JSON file"""
    with open('services.json', 'w', encoding='utf-8') as f:
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
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Service name required'}), 400
    config['services'][name] = data
    save_service_config(config)
    return jsonify({'success': True, 'service': data})

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
    

    # Parse EXCLUDED_SERVICES for both container and container:port
    excluded_services_raw = os.environ.get('EXCLUDED_SERVICES', '').split(',')
    excluded_services_raw = [name.strip() for name in excluded_services_raw if name.strip()]
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
    config = load_service_config()
    category_config = config.get('categories', {})
    # Determine category display order based on persisted order
    configured_order = config.get('categoryOrder', [])
    # Final order: configured order, followed by any categories not listed yet
    present_categories = list(categories.keys())
    category_order = [c for c in configured_order if c in present_categories]
    for c in present_categories:
        if c not in category_order:
            category_order.append(c)
    
    app_title = os.environ.get('APPTITLE', 'Docker Services Hub')
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

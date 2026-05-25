# Docker Services Hub

A Flask web application that provides a beautiful, futuristic interface for managing and accessing Docker services running on your server.

## Features

- 🚀 **Live Development**: Changes to code are reflected immediately without rebuilding
- 🎨 **Futuristic Dark UI**: Modern, responsive design with dark mode
- 📊 **Service Categorization**: Organize services into custom categories
- 🔧 **Service Exclusion**: Hide services in an "Other Services" section
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🔄 **Auto-refresh**: Automatically refreshes every 30 seconds

## Configuration

### Service Customization

The application uses `services.json` to configure service information. Users can easily modify this file to:

- Change service names and descriptions
- Customize service icons
- Organize services into custom categories
- Add an optional root path such as `/admin` for services hosted below the port root
- Add new services

#### JSON Structure

```json
{
  "categories": {
    "Category Name": {
      "icon": "📊",
      "name": "Category Display Name"
    }
  },
  "services": {
    "container-name": {
      "name": "Display Name",
      "description": "Service description",
      "icon": "📊",
      "root_path": "/admin",
      "category": "Category Name"
    }
  },
  "defaults": {
    "name": "Docker service",
    "description": "Docker service",
    "icon": "🐳",
    "category": "Other"
  }
}
```

#### Example Configuration

```json
{
  "categories": {
    "Monitoring": {
      "icon": "📊",
      "name": "Monitoring"
    },
    "Custom Apps": {
      "icon": "🎯",
      "name": "Custom Applications"
    }
  },
  "services": {
    "cadvisor": {
      "name": "cAdvisor",
      "description": "Container Advisor - Resource monitoring and performance analysis",
      "icon": "📊",
      "category": "Monitoring"
    },
    "pihole": {
      "name": "Pi-hole",
      "description": "Network-wide ad blocker",
      "icon": "🛡️",
      "root_path": "/admin",
      "category": "Custom Apps"
    },
    "my-custom-app": {
      "name": "My Custom App",
      "description": "A custom application I built",
      "icon": "🎯",
      "category": "Custom Apps"
    }
  },
  "defaults": {
    "name": "Docker service",
    "description": "Docker service",
    "icon": "🐳",
    "category": "Other"
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APPTITLE` | Web page title | "Docker Services Hub" |
| `EXCLUDED_SERVICES` | Comma-separated list of container names and/or container:port pairs to exclude. If a container name is listed, all its ports are excluded. If a container:port is listed, only that port is excluded. | "" |
| `FLASK_ENV` | Flask environment (development/production) | "development" |

#### Excluding Services and Ports

You can exclude entire containers or only specific ports from the main dashboard. Excluded services will appear in the "Other Services" section.

**Examples:**

- `EXCLUDED_SERVICES=fluentd,git` → All ports for `fluentd` and `git` are excluded.
- `EXCLUDED_SERVICES=transmission:51413` → Only port 51413 for the `transmission` container is excluded; other ports for `transmission` will still show as normal.
- `EXCLUDED_SERVICES=fluentd,transmission:51413,git` → Combination of both behaviors.

You can mix and match container names and container:port pairs, separated by commas.

### Example docker-compose.yml Configuration

```yaml
flask-hub:
  build: ./docker-hub
  container_name: flask-hub
  ports:
    - "80:5000"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - ./docker-hub:/app
  environment:
    - FLASK_ENV=development
    - APPTITLE=My Docker Hub
    - EXCLUDED_SERVICES=fluentd,transmission:51413,git
  restart: unless-stopped
```

## Development

### Live Development

The application is configured for live development:

1. **No rebuilding required** for code changes
2. **JSON configuration changes** are reflected immediately
3. **Template changes** are reflected immediately
4. **CSS/JS changes** require browser refresh

### File Structure

```
docker-hub/
├── app.py              # Main Flask application
├── services.json       # Service configuration (user-editable)
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container definition
├── templates/
│   └── index.html     # Main template
└── static/
    ├── css/
    │   └── style.css  # Styles
    └── js/
        └── app.js     # JavaScript
```

### Adding New Services

1. **Add container to docker-compose.yml**
2. **Add service configuration to services.json**:
   ```json
   "new-container-name": {
     "name": "Friendly Name",
     "description": "What this service does",
     "icon": "🎯",
     "root_path": "/admin",
     "category": "Your Category"
   }
   ```
3. **Restart or the service will appear automatically**

### Custom Categories

Create custom categories by defining them in the `categories` section:

```json
{
  "categories": {
    "My Custom Category": {
      "icon": "🎯",
      "name": "My Custom Category"
    },
    "Another Category": {
      "icon": "⚡",
      "name": "Another Category"
    }
  },
  "services": {
    "service1": {
      "category": "My Custom Category"
    },
    "service2": {
      "category": "Another Category"
    }
  }
}
```

Categories are automatically created and displayed in the UI. If a category is not defined in the `categories` section, it will use the default icon (🐳).

## API Endpoints

- `/` - Main dashboard
- `/health` - Health check endpoint
- `/debug` - Debug information (containers, services)

## Icons

Use any emoji as service icons. Some suggestions:

- 📊 Monitoring
- 🛠️ Development
- 📚 Version Control
- 🌐 Web Services
- 🚀 Management
- 🧪 Testing
- 🎯 Custom Apps
- 📝 Logging

## Troubleshooting

### Service Not Appearing

1. Check if container has exposed ports
2. Verify container name in `services.json`
3. Check Docker socket permissions
4. Review application logs: `docker logs flask-hub`

### JSON Configuration Issues

1. Validate JSON syntax
2. Check file permissions
3. Ensure UTF-8 encoding
4. Review application logs for parsing errors

### Live Development Not Working

1. Verify volume mount: `./docker-hub:/app`
2. Check `FLASK_ENV=development`
3. Ensure file permissions are correct
4. Restart container if needed

## License

This project is open source and available under the MIT License.

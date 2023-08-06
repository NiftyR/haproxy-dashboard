from flask import Flask, render_template, request
from flask import Flask, render_template, request, redirect, url_for
import subprocess

app = Flask(__name__)

def is_frontend_exist(frontend_name, frontend_ip, frontend_port):
    with open('/etc/haproxy/haproxy.cfg', 'r') as haproxy_cfg:
        frontend_found = False
        for line in haproxy_cfg:
            if line.strip().startswith('frontend'):
                _, existing_frontend_name = line.strip().split(' ', 1)
                if existing_frontend_name.strip() == frontend_name:
                    frontend_found = True
                else:
                    frontend_found = False
            elif frontend_found and line.strip().startswith('bind'):
                _, bind_info = line.strip().split(' ', 1)
                existing_ip, existing_port = bind_info.split(':', 1)
                if existing_ip.strip() == frontend_ip and existing_port.strip() == frontend_port:
                    return True
    return False


def is_backend_exist(backend_name):
    with open('/etc/haproxy/haproxy.cfg', 'r') as haproxy_cfg:
        backend_found = False
        for line in haproxy_cfg:
            if line.strip().startswith('backend'):
                _, existing_backend_name = line.strip().split(' ', 1)
                if existing_backend_name.strip() == backend_name:
                    backend_found = True
                else:
                    backend_found = False
    return backend_found
                    
# Function to update HAProxy config file


def update_haproxy_config(frontend_name, frontend_ip, frontend_port, lb_method, protocol, backend_name, backend_servers, health_check, health_check_link, sticky_session, sticky_session_type, is_acl, acl_name, acl_backend_name, use_ssl,ssl_cert_path ):
    
    if is_backend_exist(backend_name):
            return f"Backend {backend_name} already exists. Cannot add duplicate."
    
    with open('/etc/haproxy/haproxy.cfg', 'a') as haproxy_cfg:
        haproxy_cfg.write(f"\nfrontend {frontend_name}\n")
        if is_frontend_exist(frontend_name, frontend_ip, frontend_port):
            return "Frontend or Port already exists. Cannot add duplicate."
        haproxy_cfg.write(f"    bind {frontend_ip}:{frontend_port}")
        if use_ssl:
            haproxy_cfg.write(f" ssl crt {ssl_cert_path}")
        haproxy_cfg.write("\n")
        haproxy_cfg.write(f"    mode {protocol}\n")
        haproxy_cfg.write(f"    balance {lb_method}\n")
        if is_acl:
            haproxy_cfg.write(f"    acl {acl_name}\n")
            haproxy_cfg.write(f"    use_backend {acl_backend_name} if {acl_name}\n")
        haproxy_cfg.write(f"    default_backend {backend_name}\n")

    with open('/etc/haproxy/haproxy.cfg', 'a') as haproxy_cfg:
        haproxy_cfg.write(f"\nbackend {backend_name}\n")
        
        if sticky_session and sticky_session_type == 'cookie':
            haproxy_cfg.write("    cookie SERVERID insert indirect nocache\n")
        if sticky_session and sticky_session_type == 'stick-table':
            haproxy_cfg.write("    stick-table type ip size 200k expire 5m\n")
            haproxy_cfg.write("    stick on src\n")
        if protocol == 'http':
            if health_check:
                haproxy_cfg.write(f"    option httpchk GET {health_check_link}\n")
        for backend_server_info in backend_servers:
            backend_server_name, backend_server_ip, backend_server_port = backend_server_info
            haproxy_cfg.write(f"    server {backend_server_name} {backend_server_ip}:{backend_server_port} check")
            if sticky_session and sticky_session_type == 'cookie':
                haproxy_cfg.write(f" cookie {backend_server_name}")
            haproxy_cfg.write("\n")

    return "Frontend and Backend added successfully."


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        frontend_name = request.form['frontend_name']
        frontend_ip = request.form['frontend_ip']
        frontend_port = request.form['frontend_port']
        lb_method = request.form['lb_method']
        protocol = request.form['protocol']
        backend_name = request.form['backend_name']
        backend_server_names = request.form.getlist('backend_server_names')
        backend_server_ips = request.form.getlist('backend_server_ips')
        backend_server_ports = request.form.getlist('backend_server_ports')
        is_acl = 'add_acl' in request.form
        acl_name = request.form['acl'] if 'acl' in request.form else ''
        acl_backend_name = request.form['backend_name_acl'] if 'backend_name_acl' in request.form else ''
        use_ssl = 'ssl_checkbox' in request.form
        ssl_cert_path = request.form['ssl_cert_path']
      
        # Combine backend server info into a list of tuples (name, ip, port)
        backend_servers = zip(backend_server_names, backend_server_ips, backend_server_ports)

        # Check if frontend or port already exists
        if is_frontend_exist(frontend_name, frontend_ip, frontend_port):
            return render_template('index.html', message="Frontend or Port already exists. Cannot add duplicate.")

        # Get health check related fields if the protocol is HTTP
        health_check = False
        health_check_link = ""
        if protocol == 'http':
            health_check = 'health_check' in request.form
            if health_check:
                health_check_link = request.form['health_check_link']

        # Get sticky session related fields
        sticky_session = False
        sticky_session_type = ""
        if 'sticky_session' in request.form:
            sticky_session = True
            sticky_session_type = request.form['sticky_session_type']

        # Update the HAProxy config file
        message = update_haproxy_config(frontend_name, frontend_ip, frontend_port, lb_method, protocol, backend_name, backend_servers, health_check, health_check_link, sticky_session, sticky_session_type, is_acl, acl_name, acl_backend_name, use_ssl, ssl_cert_path )
        return render_template('index.html', message=message)

    return render_template('index.html')

import subprocess

@app.route('/edit', methods=['GET', 'POST'])
def edit_haproxy_config():
    if request.method == 'POST':
        edited_config = request.form['haproxy_config']
        # Save the edited config to the haproxy.cfg file
        with open('/etc/haproxy/haproxy.cfg', 'w') as f:
            f.write(edited_config)

        if 'save_check' in request.form:
            # Run haproxy -c -V -f to check the configuration
            check_result = subprocess.run(['haproxy', '-c', '-V', '-f', '/etc/haproxy/haproxy.cfg'], capture_output=True, text=True)
            check_output = check_result.stdout

            # Check if there was an error, and if so, append it to the output
            if check_result.returncode != 0:
                error_message = check_result.stderr
                check_output += f"\n\nError occurred:\n{error_message}"

        elif 'save_reload' in request.form:
            # Run haproxy -c -V -f to check the configuration
            check_result = subprocess.run(['haproxy', '-c', '-V', '-f', '/etc/haproxy/haproxy.cfg'], capture_output=True, text=True)
            check_output = check_result.stdout

            # Check if there was an error, and if so, append it to the output
            if check_result.returncode != 0:
                error_message = check_result.stderr
                check_output += f"\n\nError occurred:\n{error_message}"
            else:
                # If no error, run haproxy -D -f to reload HAProxy
                reload_result = subprocess.run(['haproxy', '-D', '-f', '/etc/haproxy/haproxy.cfg'], capture_output=True, text=True)
                check_output += f"\n\nHAProxy Reload Output:\n{reload_result.stdout}"

        return render_template('edit.html', config_content=edited_config, check_output=check_output)

    # Read the current contents of haproxy.cfg
    with open('/etc/haproxy/haproxy.cfg', 'r') as f:
        config_content = f.read()

    return render_template('edit.html', config_content=config_content)





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
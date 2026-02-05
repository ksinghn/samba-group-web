from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import paramiko
import io
import os
import shlex

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')

# --- SSH helper ---

def get_connection_info():
    return {
        'host': session.get('ssh_host'),
        'username': session.get('ssh_user'),
        'password': session.get('ssh_pass'),
        'port': int(session.get('ssh_port', 22)),
    }

class SSHExecError(Exception):
    pass


def execute_ssh(command, timeout=60):
    info = get_connection_info()
    if not info['host'] or not info['username'] or not info['password']:
        raise SSHExecError('Connection info not set. Please set IP, username and password.')

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(info['host'], port=info['port'], username=info['username'], password=info['password'], look_for_keys=False, allow_agent=False, timeout=10)
        command = "sudo -S -p '' %s" % command
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        # Send password for sudo
        stdin.write(info['password'] + '\n')
        stdin.flush()
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, out, err
    finally:
        client.close()

# --- Utility parsers ---

def parse_user_show(output):
    # Parse lines like: Email: user@example.com  or MemberOf: CN=demo.group2,CN=Users
    email = ''
    groups = []
    for line in output.splitlines():
        line = line.strip()
        if line.lower().startswith('mail:') or line.lower().startswith('email:') or line.lower().startswith('mail address:'):
            parts = line.split(':', 1)
            if len(parts) > 1:
                email = parts[1].strip()
        if line.startswith('MemberOf:'):
            parts = line.split(':', 1)
            if len(parts) > 1:
                memberof = parts[1].strip()
                # comma separated; take CN=... pieces
                items = [x.strip() for x in memberof.split(',')]
                for item in items:
                    if item.upper().startswith('CN='):
                        cn = item.split('=',1)[1]
                        groups.append(cn)
    return email, groups

# --- Routes ---

@app.route('/')
def index():
    return redirect(url_for('users_page'))

@app.route('/set_connection', methods=['POST'])
def set_connection():
    data = request.form
    session['ssh_host'] = data.get('host')
    session['ssh_user'] = data.get('username')
    session['ssh_pass'] = data.get('password')
    session['ssh_port'] = data.get('port', 22)
    return jsonify({'status': 'ok'})

@app.route('/connection_info')
def connection_info():
    info = get_connection_info()
    ok = bool(info['host'] and info['username'] and info['password'])
    return jsonify({'connected': ok, 'host': info['host'], 'username': info['username']})

# --- Users ---
@app.route('/users')
def users_page():
    return render_template('users.html')

@app.route('/api/users')
def api_users():
    try:
        status, out, err = execute_ssh('samba-tool user list')
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    if status != 0:
        return jsonify({'error': err or out}), 500
    users = [u.strip() for u in out.splitlines() if u.strip()]
    result = []
    for u in users:
        status, out_u, err_u = execute_ssh(f"samba-tool user show {shlex.quote(u)}")
        email, groups = parse_user_show(out_u)
        result.append({'username': u, 'email': email, 'groups': groups})
    return jsonify({'users': result})

@app.route('/api/create_user', methods=['POST'])
def api_create_user():
    data = request.json or request.form
    first = data.get('first_name', '').strip()
    last = data.get('last_name', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    if not (first and last and password):
        return jsonify({'error': 'First name, last name and password are required'}), 400
    username = (first + '.' + last).lower().replace(' ', '')
    # Build samba-tool command
    cmd = f"samba-tool user create {shlex.quote(username)} {shlex.quote(password)} --given-name={shlex.quote(first)} --surname={shlex.quote(last)} --mail-address={shlex.quote(email)}"
    try:
        status, out, err = execute_ssh(cmd)
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    code = 200 if status == 0 else 500
    return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code

# --- Groups ---
@app.route('/groups')
def groups_page():
    return render_template('groups.html')

@app.route('/api/groups')
def api_groups():
    try:
        status, out, err = execute_ssh('samba-tool group list')
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    if status != 0:
        return jsonify({'error': err or out}), 500
    groups = [g.strip() for g in out.splitlines() if g.strip()]
    result = []
    for g in groups:
        # Try to get description; different samba versions may use different output
        status, out_g, err_g = execute_ssh(f"samba-tool group show {shlex.quote(g)}")
        desc = ''
        if status == 0:
            for line in out_g.splitlines():
                if line.strip().lower().startswith('description:'):
                    parts = line.split(':',1)
                    if len(parts) > 1:
                        desc = parts[1].strip()
                        break
        result.append({'name': g, 'description': desc})
    return jsonify({'groups': result})

@app.route('/api/create_group', methods=['POST'])
def api_create_group():
    data = request.json or request.form
    name = data.get('group_name', '').strip()
    desc = data.get('group_description', '').strip()
    if not name:
        return jsonify({'error': 'Group name required'}), 400
    # Try with description first
    cmd = f"samba-tool group add {shlex.quote(name)} --description={shlex.quote(desc)}"
    try:
        status, out, err = execute_ssh(cmd)
        if status != 0:
            # Fallback without description
            status, out, err = execute_ssh(f"samba-tool group add {shlex.quote(name)}")
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    code = 200 if status == 0 else 500
    return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code

# --- Group members ---
@app.route('/group-members')
def group_members_page():
    return render_template('group_members.html')

@app.route('/api/group_members')
def api_group_members():
    group = request.args.get('group')
    if not group:
        return jsonify({'error': 'group parameter required'}), 400
    try:
        status, out, err = execute_ssh(f"samba-tool group listmembers {shlex.quote(group)}")
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    if status != 0:
        return jsonify({'error': err or out}), 500
    members = [l.strip() for l in out.splitlines() if l.strip()]
    # get all users
    status_u, out_u, err_u = execute_ssh('samba-tool user list')
    users = [u.strip() for u in out_u.splitlines() if u.strip()]
    non_members = [u for u in users if u not in members]
    return jsonify({'members': members, 'non_members': non_members})

@app.route('/api/add_members', methods=['POST'])
def api_add_members():
    data = request.json or request.form
    group = data.get('group')
    users = data.get('users') or []
    if isinstance(users, str):
        users = [users]
    if not group or not users:
        return jsonify({'error': 'group and users required'}), 400
    cmd = 'samba-tool group addmembers ' + shlex.quote(group) + ' ' + ' '.join(shlex.quote(u) for u in users)
    try:
        status, out, err = execute_ssh(cmd)
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    code = 200 if status == 0 else 500
    return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code

@app.route('/api/remove_members', methods=['POST'])
def api_remove_members():
    data = request.json or request.form
    group = data.get('group')
    users = data.get('users') or []
    if isinstance(users, str):
        users = [users]
    if not group or not users:
        return jsonify({'error': 'group and users required'}), 400
    cmd = 'samba-tool group removemembers ' + shlex.quote(group) + ' ' + ' '.join(shlex.quote(u) for u in users)
    try:
        status, out, err = execute_ssh(cmd)
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    code = 200 if status == 0 else 500
    return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code

# --- Run arbitrary script (optional) ---
@app.route('/api/run_script', methods=['POST'])
def api_run_script():
    data = request.json or request.form
    script_path = data.get('script_path')
    if not script_path:
        return jsonify({'error': 'script_path required'}), 400
    # run with bash -l -c to preserve environment
    cmd = f"bash -l -c {shlex.quote(script_path)}"
    try:
        status, out, err = execute_ssh(cmd, timeout=300)
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    code = 200 if status == 0 else 500
    return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

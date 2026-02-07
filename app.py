from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from config import Config
from forms import LoginForm, UserForm, GroupForm
from utils import parse_user_show
import paramiko
import os
import shlex
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

# --- Authentication Decorator ---

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

# --- SSH Connection Helper ---

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
    """Execute a command on the remote host via SSH with sudo."""
    info = get_connection_info()
    if not info['host'] or not info['username'] or not info['password']:
        raise SSHExecError('Connection info not set. Please configure SSH connection.')

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            info['host'],
            port=info['port'],
            username=info['username'],
            password=info['password'],
            look_for_keys=False,
            allow_agent=False,
            timeout=10
        )
        command = "sudo -S -p '' %s" % command
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        stdin.write(info['password'] + '\n')
        stdin.flush()
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, out, err
    finally:
        client.close()

# --- Login Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.password.data == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('index'))
        flash('Invalid password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Main Routes ---

@app.route('/')
def index():
    form = LoginForm()
    return render_template('index.html', login_form=form)

@app.route('/set_connection', methods=['POST'])
@login_required
def set_connection():
    data = request.form
    session['ssh_host'] = data.get('host')
    session['ssh_user'] = data.get('username')
    session['ssh_pass'] = data.get('password')
    session['ssh_port'] = data.get('port', '22')
    flash('SSH connection configured', 'success')
    return redirect(url_for('index'))

@app.route('/connection_info')
@login_required
def connection_info():
    info = get_connection_info()
    ok = bool(info['host'] and info['username'] and info['password'])
    return jsonify({
        'connected': ok,
        'host': info['host'],
        'username': info['username']
    })

# --- Users Management ---

@app.route('/users', methods=['GET', 'POST'])
@login_required
def users_page():
    form = UserForm()
    result = None
    users = []
    
    if form.validate_on_submit():
        first = form.first_name.data.strip()
        last = form.last_name.data.strip()
        password = form.password.data.strip()
        email = form.email.data.strip()
        
        if not (first and last and password):
            flash('First name, last name and password are required', 'danger')
        else:
            username = (first + '.' + last).lower().replace(' ', '')
            cmd = f"samba-tool user create {shlex.quote(username)} {shlex.quote(password)} --given-name={shlex.quote(first)} --surname={shlex.quote(last)}"
            if email:
                cmd += f" --mail-address={shlex.quote(email)}"
            
            try:
                status, out, err = execute_ssh(cmd)
                result = (status, out, err)
                if status == 0:
                    flash('User created successfully', 'success')
                else:
                    flash('Failed to create user', 'danger')
            except SSHExecError as e:
                flash(str(e), 'danger')
    
    # List users
    try:
        status, out, err = execute_ssh('samba-tool user list')
        if status == 0:
            users = [u.strip() for u in out.splitlines() if u.strip()]
    except SSHExecError:
        flash('Could not retrieve user list', 'warning')
    
    return render_template('users.html', form=form, users=users, result=result)

@app.route('/api/users')
@login_required
def api_users():
    try:
        status, out, err = execute_ssh('samba-tool user list')
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    
    if status != 0:
        return jsonify({'error': err or out}), 500
    
    users_list = [u.strip() for u in out.splitlines() if u.strip()]
    result = []
    
    for u in users_list:
        try:
            status, out_u, err_u = execute_ssh(f"samba-tool user show {shlex.quote(u)}")
            email, groups = parse_user_show(out_u)
            result.append({'username': u, 'email': email, 'groups': groups})
        except SSHExecError:
            result.append({'username': u, 'email': '', 'groups': []})
    
    return jsonify({'users': result})

# --- Groups Management ---

@app.route('/groups', methods=['GET', 'POST'])
@login_required
def groups_page():
    form = GroupForm()
    result = None
    groups = []
    
    if form.validate_on_submit():
        name = form.group_name.data.strip()
        desc = form.group_description.data.strip()
        
        if not name:
            flash('Group name required', 'danger')
        else:
            cmd = f"samba-tool group add {shlex.quote(name)}"
            if desc:
                cmd += f" --description={shlex.quote(desc)}"
            
            try:
                status, out, err = execute_ssh(cmd)
                result = (status, out, err)
                if status == 0:
                    flash('Group created successfully', 'success')
                else:
                    flash('Failed to create group', 'danger')
            except SSHExecError as e:
                flash(str(e), 'danger')
    
    # List groups
    try:
        status, out, err = execute_ssh('samba-tool group list')
        if status == 0:
            groups = [g.strip() for g in out.splitlines() if g.strip()]
    except SSHExecError:
        flash('Could not retrieve group list', 'warning')
    
    return render_template('groups.html', form=form, groups=groups, result=result)

@app.route('/api/groups')
@login_required
def api_groups():
    try:
        status, out, err = execute_ssh('samba-tool group list')
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400
    
    if status != 0:
        return jsonify({'error': err or out}), 500
    
    groups_list = [g.strip() for g in out.splitlines() if g.strip()]
    result = []
    
    for g in groups_list:
        desc = ''
        try:
            status, out_g, err_g = execute_ssh(f"samba-tool group show {shlex.quote(g)}")
            if status == 0:
                for line in out_g.splitlines():
                    if line.strip().lower().startswith('description:'):
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            desc = parts[1].strip()
                            break
        except SSHExecError:
            pass
        
        result.append({'name': g, 'description': desc})
    
    return jsonify({'groups': result})

# --- Group Members Management ---

@app.route('/group-members')
@login_required
def group_members_page():
    return render_template('group_members.html')

@app.route('/api/group_members')
@login_required
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
    
    try:
        status_u, out_u, err_u = execute_ssh('samba-tool user list')
        users = [u.strip() for u in out_u.splitlines() if u.strip()]
    except SSHExecError:
        users = []
    
    non_members = [u for u in users if u not in members]
    return jsonify({'members': members, 'non_members': non_members})

@app.route('/api/add_members', methods=['POST'])
@login_required
def api_add_members():
    data = request.json or request.form
    group = data.get('group')
    users = data.get('users') or []
    
    if isinstance(users, str):
        users = [users]
    if not group or not users:
        return jsonify({'error': 'group and users required'}), 400
    
    cmd = f"samba-tool group addmembers {shlex.quote(group)} {', '.join(shlex.quote(u) for u in users)}"
    
    try:
        status, out, err = execute_ssh(cmd)
        code = 200 if status == 0 else 500
        return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/remove_members', methods=['POST'])
@login_required
def api_remove_members():
    data = request.json or request.form
    group = data.get('group')
    users = data.get('users') or []
    
    if isinstance(users, str):
        users = [users]
    if not group or not users:
        return jsonify({'error': 'group and users required'}), 400
    
    cmd = f"samba-tool group removemembers {shlex.quote(group)} {', '.join(shlex.quote(u) for u in users)}"
    
    try:
        status, out, err = execute_ssh(cmd)
        code = 200 if status == 0 else 500
        return jsonify({'exit_status': status, 'stdout': out, 'stderr': err}), code
    except SSHExecError as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)

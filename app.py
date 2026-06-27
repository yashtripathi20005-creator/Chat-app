from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room, send
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active users and their rooms
active_users = {}  # {session_id: {'username': name, 'room': room}}
user_sid_map = {}  # {username: sid}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    session['sid'] = request.sid

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    username = active_users.get(request.sid, {}).get('username')
    room = active_users.get(request.sid, {}).get('room')
    
    if username and room:
        # Remove user from room
        leave_room(room)
        # Remove from active users
        if request.sid in active_users:
            del active_users[request.sid]
        if username in user_sid_map:
            del user_sid_map[username]
        
        # Notify others in the room
        emit('user_left', {
            'username': username,
            'time': datetime.now().strftime('%I:%M %p')
        }, to=room)
        
        # Update user list
        room_users = [user['username'] for user in active_users.values() if user.get('room') == room]
        emit('user_list', room_users, to=room)

@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    room = data.get('room')
    
    if not username or not room:
        emit('error', {'message': 'Username and room are required'})
        return
    
    # Check if username is already taken in this room
    for sid, user in active_users.items():
        if user.get('username') == username and user.get('room') == room:
            emit('error', {'message': 'Username is already taken in this room'})
            return
    
    # Store user info
    active_users[request.sid] = {
        'username': username,
        'room': room
    }
    user_sid_map[username] = request.sid
    
    # Join the room
    join_room(room)
    
    # Send join message to everyone in the room
    emit('user_joined', {
        'username': username,
        'time': datetime.now().strftime('%I:%M %p')
    }, to=room)
    
    # Send updated user list
    room_users = [user['username'] for user in active_users.values() if user.get('room') == room]
    emit('user_list', room_users, to=room)
    
    # Send confirmation to the user
    emit('joined', {
        'username': username,
        'room': room,
        'message': f'You have joined room: {room}'
    })

@socketio.on('message')
def handle_message(data):
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        emit('error', {'message': 'Missing required fields'})
        return
    
    # Broadcast message to everyone in the room
    emit('new_message', {
        'username': username,
        'message': message,
        'time': datetime.now().strftime('%I:%M %p')
    }, to=room)

@socketio.on('typing')
def handle_typing(data):
    username = data.get('username')
    room = data.get('room')
    is_typing = data.get('is_typing', False)
    
    emit('user_typing', {
        'username': username,
        'is_typing': is_typing
    }, to=room, include_self=False)

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    recipient = data.get('recipient')
    message = data.get('message')
    
    if not all([sender, recipient, message]):
        emit('error', {'message': 'Missing required fields'})
        return
    
    recipient_sid = user_sid_map.get(recipient)
    sender_room = active_users.get(request.sid, {}).get('room')
    
    if recipient_sid:
        # Send to recipient
        emit('private_message', {
            'sender': sender,
            'message': message,
            'time': datetime.now().strftime('%I:%M %p')
        }, to=recipient_sid)
        
        # Send confirmation to sender
        emit('private_message_sent', {
            'recipient': recipient,
            'message': message,
            'time': datetime.now().strftime('%I:%M %p')
        })
    else:
        emit('error', {'message': f'User {recipient} is not online'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

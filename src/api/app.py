import sys
import os
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exc as sqlalchemy_exc
from datetime import datetime

from brain_processor import BrainProcessor
from config import FLASK_PORT, LOGSEQ_NOTES_DIR, VECTOR_DB_PATH, DEFAULT_MODEL, create_directories, JWT_SECRET_KEY
from src.db.database import init_db, get_db
from src.db.models import User, Reminder, Friendship, SharedReminder, FriendSpace, FriendSpaceMember, Task, Tag, TaskTag, TaskAssignment
from src.auth import hash_password, verify_password

# Create necessary directories
create_directories()

# Initialize database
init_db()

# Initialize Flask app
app = Flask(__name__,
            template_folder='../../templates',
            static_folder='../../static')
CORS(app)  # Enable CORS for all routes

# Configure Flask-JWT-Extended
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
jwt = JWTManager(app)

# Initialize the brain processor
brain = BrainProcessor(
    logseq_dir=LOGSEQ_NOTES_DIR,
    vector_db_path=VECTOR_DB_PATH,
    model=DEFAULT_MODEL
)

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """Get the status of the brain processor"""
    return jsonify({
        "is_ready": brain.is_ready(),
        "components": {
            "parser": brain.parser is not None,
            "llm": brain.llm is not None,
            "vector_store": brain.vector_store is not None
        }
    })

@app.route('/api/process', methods=['POST'])
def process_notes():
    """Process all notes from Logseq"""
    stats = brain.process_all_notes()
    return jsonify(stats)

@app.route('/api/search', methods=['GET', 'POST'])
def search():
    """Search the brain"""
    if request.method == 'POST':
        data = request.json
        query = data.get('query', '')
        collection = data.get('collection', 'all')
        limit = int(data.get('limit', 5))
    else:
        query = request.args.get('query', '')
        collection = request.args.get('collection', 'all')
        limit = int(request.args.get('limit', 5))
    
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    results = brain.search_brain(query, collection=collection, limit=limit)
    return jsonify(results)

@app.route('/api/search/date', methods=['GET', 'POST'])
def search_date():
    """Search journal entries by date"""
    if request.method == 'POST':
        data = request.json
        date_str = data.get('date', '')
        limit = int(data.get('limit', 5))
    else:
        date_str = request.args.get('date', '')
        limit = int(request.args.get('limit', 5))
    
    if not date_str:
        return jsonify({"error": "Date is required"}), 400
    
    results = brain.search_by_date(date_str, limit=limit)
    return jsonify(results)

@app.route('/api/enhance', methods=['POST'])
def enhance_note():
    """Enhance a note using the LLM"""
    app.logger.info("Received request for /api/enhance")
    try:
        data = request.json
        if not data:
            app.logger.warning("Invalid JSON payload received")
            return jsonify({"error": "Invalid JSON payload"}), 400
            
        content = data.get('content', '')
        task = data.get('task', 'enhance')
        
        if not content:
            app.logger.warning("Content is required but not provided")
            return jsonify({"error": "Content is required"}), 400
        
        app.logger.info(f"Enhancing note with task: {task}, content length: {len(content)}")
        
        # Check if the brain is ready
        if not brain.is_ready():
            app.logger.error("Brain not ready for enhance_note request")
            return jsonify({"error": "Brain is not ready. Make sure all services are running."}), 503
        
        app.logger.info("Calling brain.enhance_note...")
        result = brain.enhance_note(content, task=task)
        app.logger.info(f"Received result from brain.enhance_note: {result}")
        
        if result and 'error' in result:
            app.logger.error(f"Error enhancing note reported by brain: {result['error']}")
            # Ensure we return a 500 if brain.enhance_note signals an error
            return jsonify(result), 500 
            
        # Ensure result is not None before returning
        if result is None:
            app.logger.error("brain.enhance_note returned None")
            return jsonify({"error": "Internal server error: No response from brain processing."}), 500

        app.logger.info("Successfully processed enhance request, returning result.")
        return jsonify(result)
        
    except Exception as e:
        # Log the full exception traceback
        app.logger.error(f"Exception in enhance_note route: {str(e)}", exc_info=True) 
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/models', methods=['GET'])
def list_models():
    """List available LLM models"""
    if brain.llm:
        models = brain.llm.list_models()
        return jsonify(models)
    return jsonify({"error": "LLM is not initialized"}), 500

@app.route('/api/notes/stats', methods=['GET'])
def notes_stats():
    """Get statistics about processed notes"""
    try:
        stats_files = list(Path('./data/processed').glob('processing_stats_*.json'))
        
        if not stats_files:
            return jsonify({"message": "No processing stats available yet"}), 200
        
        # Get the most recent stats file
        latest_stats_file = max(stats_files, key=lambda p: p.stat().st_mtime)
        
        with open(latest_stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not brain.is_ready():
        print("Warning: BrainProcessor is not fully initialized. Some features may not work.")
    
    print(f"Starting Personal Brain API on port {FLASK_PORT}")
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=True)


@app.route('/api/users/register', methods=['POST'])
def register_user():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify(message="Username, email, and password are required"), 400

    # Basic validation (can be expanded)
    if len(password) < 6:
        return jsonify(message="Password must be at least 6 characters long"), 400

    db = next(get_db())
    try:
        existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            return jsonify(message="Username or email already exists"), 400

        hashed = hash_password(password)
        new_user = User(username=username, email=email, password_hash=hashed)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return jsonify(message="User registered successfully", user={"id": new_user.id, "username": new_user.username}), 201
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error during registration: {e}")
        return jsonify(message="Error during registration"), 500
    finally:
        db.close()


# Friendship API Endpoints

@app.route('/api/friends/requests', methods=['POST'])
@jwt_required()
def send_friend_request():
    current_user_id = get_jwt_identity()
    data = request.json
    target_username = data.get('target_username') # Or target_user_id

    if not target_username:
        return jsonify(message="Target username is required"), 400

    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.username == target_username).first()
        if not target_user:
            return jsonify(message="Target user not found"), 404

        if target_user.id == current_user_id:
            return jsonify(message="Cannot send friend request to yourself"), 400

        # Check if a request already exists (either way)
        existing_request = db.query(Friendship).filter(
            or_(
                and_(Friendship.requester_id == current_user_id, Friendship.receiver_id == target_user.id),
                and_(Friendship.requester_id == target_user.id, Friendship.receiver_id == current_user_id)
            )
        ).first()

        if existing_request:
            if existing_request.status == "pending":
                return jsonify(message="Friend request already pending"), 409
            elif existing_request.status == "accepted":
                return jsonify(message="You are already friends with this user"), 409
            elif existing_request.status == "rejected" and existing_request.requester_id == current_user_id :
                 # Allow re-sending if current user's previous request was rejected
                 db.delete(existing_request)
                 db.commit()
            elif existing_request.status == "rejected" and existing_request.receiver_id == current_user_id :
                return jsonify(message="You have a rejected request from this user. They must send a new request."), 409


        new_request = Friendship(
            requester_id=current_user_id,
            receiver_id=target_user.id,
            status="pending"
        )
        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        return jsonify(message="Friend request sent", request=new_request.to_dict()), 201
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error sending friend request: {e}")
        return jsonify(message="Error sending friend request"), 500
    finally:
        db.close()

@app.route('/api/friends/requests/<int:request_id>/respond', methods=['POST'])
@jwt_required()
def respond_to_friend_request(request_id):
    current_user_id = get_jwt_identity()
    data = request.json
    action = data.get('action') # "accept" or "reject"

    if action not in ["accept", "reject"]:
        return jsonify(message="Invalid action. Must be 'accept' or 'reject'"), 400

    db = next(get_db())
    try:
        friend_request = db.query(Friendship).filter(
            Friendship.id == request_id,
            Friendship.receiver_id == current_user_id,
            Friendship.status == "pending"
        ).first()

        if not friend_request:
            return jsonify(message="Pending friend request not found or you are not the receiver"), 404

        if action == "accept":
            friend_request.status = "accepted"
        elif action == "reject":
            friend_request.status = "rejected"

        friend_request.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(friend_request)
        return jsonify(message=f"Friend request {action}ed", request=friend_request.to_dict()), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error responding to friend request: {e}")
        return jsonify(message="Error responding to friend request"), 500
    finally:
        db.close()

@app.route('/api/friends/requests/pending', methods=['GET'])
@jwt_required()
def list_pending_friend_requests():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        pending_requests = db.query(Friendship).filter(
            Friendship.receiver_id == current_user_id,
            Friendship.status == "pending"
        ).all()
        serialized_requests = [req.to_dict() for req in pending_requests]
        return jsonify(pending_requests=serialized_requests), 200
    except Exception as e:
        app.logger.error(f"Error listing pending friend requests: {e}")
        return jsonify(message="Error listing pending friend requests"), 500
    finally:
        db.close()

@app.route('/api/friends/requests/sent', methods=['GET'])
@jwt_required()
def list_sent_friend_requests():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        sent_requests = db.query(Friendship).filter(
            Friendship.requester_id == current_user_id,
            Friendship.status == "pending" # Can also include other statuses if needed
        ).all()
        serialized_requests = [req.to_dict() for req in sent_requests]
        return jsonify(sent_requests=serialized_requests), 200
    except Exception as e:
        app.logger.error(f"Error listing sent friend requests: {e}")
        return jsonify(message="Error listing sent friend requests"), 500
    finally:
        db.close()


@app.route('/api/friends', methods=['GET'])
@jwt_required()
def list_friends():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        accepted_friendships = db.query(Friendship).filter(
            Friendship.status == "accepted",
            or_(
                Friendship.requester_id == current_user_id,
                Friendship.receiver_id == current_user_id
            )
        ).all()

        friends = []
        for friendship in accepted_friendships:
            if friendship.requester_id == current_user_id:
                friend_user = friendship.receiver
            else:
                friend_user = friendship.requester
            
            if friend_user: # Should always be true due to FK constraints if db is consistent
                friends.append({
                    "id": friend_user.id,
                    "username": friend_user.username,
                    "email": friend_user.email, # Consider if email should be exposed here
                    "friendship_id": friendship.id,
                    "friends_since": friendship.updated_at.isoformat() # When it was accepted
                })
        return jsonify(friends=friends), 200
    except Exception as e:
        app.logger.error(f"Error listing friends: {e}")
        return jsonify(message="Error listing friends"), 500
    finally:
        db.close()

@app.route('/api/friends/<int:friendship_id>/remove', methods=['DELETE'])
@jwt_required()
def remove_friend(friendship_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        friendship = db.query(Friendship).filter(
            Friendship.id == friendship_id,
            or_(
                Friendship.requester_id == current_user_id,
                Friendship.receiver_id == current_user_id
            )
        ).first()

        if not friendship:
            return jsonify(message="Friendship not found or you are not part of it"), 404

        if friendship.status != "accepted":
            return jsonify(message="This is not an active friendship. Cannot remove."), 400

        db.delete(friendship)
        db.commit()
        return jsonify(message="Friend removed successfully"), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error removing friend: {e}")
        return jsonify(message="Error removing friend"), 500
    finally:
        db.close()


# Reminder Sharing Endpoints

@app.route('/api/reminders/<int:reminder_id>/share', methods=['POST'])
@jwt_required()
def share_reminder(reminder_id):
    current_user_id = get_jwt_identity()
    data = request.json
    share_with_username = data.get('share_with_username')

    if not share_with_username:
        return jsonify(message="share_with_username is required"), 400

    db = next(get_db())
    try:
        target_user = db.query(User).filter(User.username == share_with_username).first()
        if not target_user:
            return jsonify(message="Target user to share with not found"), 404

        if target_user.id == current_user_id:
            return jsonify(message="Cannot share a reminder with yourself"), 400

        reminder_to_share = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user_id).first()
        if not reminder_to_share:
            return jsonify(message="Reminder not found or you are not the owner"), 404

        # Friendship Check
        friendship = db.query(Friendship).filter(
            Friendship.status == "accepted",
            or_(
                and_(Friendship.requester_id == current_user_id, Friendship.receiver_id == target_user.id),
                and_(Friendship.requester_id == target_user.id, Friendship.receiver_id == current_user_id)
            )
        ).first()
        if not friendship:
            return jsonify(message="You can only share reminders with friends."), 403

        existing_share = db.query(SharedReminder).filter(
            SharedReminder.reminder_id == reminder_id,
            SharedReminder.shared_with_user_id == target_user.id
        ).first()
        if existing_share:
            return jsonify(message="Reminder already shared with this user"), 409

        new_shared_reminder = SharedReminder(
            reminder_id=reminder_id,
            shared_by_user_id=current_user_id,
            shared_with_user_id=target_user.id,
            status="active"
        )
        db.add(new_shared_reminder)
        db.commit()
        db.refresh(new_shared_reminder)
        return jsonify(message="Reminder shared successfully", share_details=new_shared_reminder.to_dict()), 201

    except Exception as e:
        db.rollback()
        app.logger.error(f"Error sharing reminder: {e}")
        return jsonify(message="Error sharing reminder"), 500
    finally:
        db.close()

@app.route('/api/reminders/shared_with_me', methods=['GET'])
@jwt_required()
def list_reminders_shared_with_me():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        shared_items = db.query(SharedReminder).filter(
            SharedReminder.shared_with_user_id == current_user_id,
            SharedReminder.status == "active" # Assuming we only want active shares
        ).all()
        
        # Ensure reminder details are loaded for serialization
        serialized_shares = []
        for sr in shared_items:
            # sr.reminder will be loaded due to relationship, then to_dict() will serialize it.
            # Explicitly loading shared_by and shared_with for usernames.
            db.session.expire(sr) # Re-fetch to ensure relationships are fresh if needed
            db.refresh(sr.reminder) # Ensure reminder details are fresh
            db.refresh(sr.shared_by)
            db.refresh(sr.shared_with)
            serialized_shares.append(sr.to_dict())
            
        return jsonify(shared_reminders=serialized_shares), 200
    except Exception as e:
        app.logger.error(f"Error listing reminders shared with me: {e}")
        return jsonify(message="Error listing shared reminders"), 500
    finally:
        db.close()

@app.route('/api/reminders/<int:reminder_id>/shared_with', methods=['GET'])
@jwt_required()
def list_users_reminder_is_shared_with(reminder_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user_id).first()
        if not reminder:
            return jsonify(message="Reminder not found or you are not the owner"), 404

        shared_with_list = db.query(SharedReminder).filter(
            SharedReminder.reminder_id == reminder_id,
            SharedReminder.status == "active"
        ).all()
        
        serialized_list = []
        for sr in shared_with_list:
            # Ensure user details are fresh
            db.refresh(sr.shared_with)
            serialized_list.append({
                "share_id": sr.id,
                "user_id": sr.shared_with_user_id,
                "username": sr.shared_with.username if sr.shared_with else "Unknown User",
                "shared_at": sr.shared_at.isoformat() if sr.shared_at else None
            })
        return jsonify(shared_with=serialized_list), 200
    except Exception as e:
        app.logger.error(f"Error listing users reminder is shared with: {e}")
        return jsonify(message="Error fetching share list"), 500
    finally:
        db.close()

@app.route('/api/shared_reminders/<int:share_id>/revoke', methods=['DELETE'])
@jwt_required()
def revoke_shared_reminder(share_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        shared_reminder_entry = db.query(SharedReminder).filter(SharedReminder.id == share_id).first()

        if not shared_reminder_entry:
            return jsonify(message="Shared reminder entry not found"), 404

        # Check if current user is the one who shared it OR the one it was shared with (allowing receiver to "unfollow")
        if shared_reminder_entry.shared_by_user_id != current_user_id and shared_reminder_entry.shared_with_user_id != current_user_id:
             return jsonify(message="You do not have permission to revoke this share"), 403

        db.delete(shared_reminder_entry)
        db.commit()
        return jsonify(message="Reminder share revoked successfully"), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error revoking shared reminder: {e}")
        return jsonify(message="Error revoking share"), 500
    finally:
        db.close()

# Friend Space API Endpoints

@app.route('/api/spaces', methods=['POST'])
@jwt_required()
def create_friend_space():
    current_user_id = get_jwt_identity()
    data = request.json
    name = data.get('name')
    description = data.get('description')

    if not name:
        return jsonify(message="Friend space name is required"), 400
    # Basic validation for name length
    if len(name) > 100 or len(name) < 3:
        return jsonify(message="Space name must be between 3 and 100 characters"), 400


    db = next(get_db())
    try:
        new_space = FriendSpace(
            name=name,
            description=description,
            owner_id=current_user_id
        )
        db.add(new_space)
        db.flush()  # Flush to get new_space.id for the member

        # Automatically add owner as the first member
        owner_member = FriendSpaceMember(
            space_id=new_space.id,
            user_id=current_user_id,
            role="owner"  # Explicitly set role for owner
        )
        db.add(owner_member)
        
        db.commit()
        db.refresh(new_space) # Refresh to load relationships like members
        # db.refresh(owner_member) # Not strictly necessary to refresh member for response

        return jsonify(message="Friend space created", space=new_space.to_dict(include_members=True)), 201
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error creating friend space: {e}")
        return jsonify(message="Error creating friend space"), 500
    finally:
        db.close()

@app.route('/api/spaces', methods=['GET'])
@jwt_required()
def list_user_friend_spaces():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        # Query FriendSpaceMember, join FriendSpace, filter by user_id
        user_memberships = db.query(FriendSpaceMember).filter(FriendSpaceMember.user_id == current_user_id).options(joinedload(FriendSpaceMember.space).joinedload(FriendSpace.owner)).all()
        
        serialized_spaces = []
        for membership in user_memberships:
            if membership.space: # Should always be true due to FK
                 # Eagerly load owner for each space if not already loaded by joinedload
                db.refresh(membership.space.owner)
                serialized_spaces.append(membership.space.to_dict()) # Pass include_members=True if desired

        return jsonify(spaces=serialized_spaces), 200
    except Exception as e:
        app.logger.error(f"Error listing user's friend spaces: {e}")
        return jsonify(message="Error listing friend spaces"), 500
    finally:
        db.close()

@app.route('/api/spaces/<int:space_id>', methods=['GET'])
@jwt_required()
def get_friend_space_details(space_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        space = db.query(FriendSpace).options(joinedload(FriendSpace.members).joinedload(FriendSpaceMember.user), joinedload(FriendSpace.owner)).filter(FriendSpace.id == space_id).first()

        if not space:
            return jsonify(message="Friend space not found"), 404

        # Authorization: Check if current_user_id is a member of this space
        is_member = db.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == space_id,
            FriendSpaceMember.user_id == current_user_id
        ).first()

        if not is_member:
            return jsonify(message="Access denied: You are not a member of this space"), 403
        
        # Refresh owner and members to ensure data is fresh for to_dict
        db.refresh(space.owner)
        for member in space.members:
            db.refresh(member.user)

        return jsonify(space=space.to_dict(include_members=True)), 200
    except Exception as e:
        app.logger.error(f"Error getting friend space details: {e}")
        return jsonify(message="Error getting friend space details"), 500
    finally:
        db.close()

@app.route('/api/spaces/<int:space_id>/members', methods=['POST'])
@jwt_required()
def add_member_to_friend_space(space_id):
    current_user_id = get_jwt_identity() # This is the owner performing the action
    data = request.json
    username_to_add = data.get('username_to_add')

    if not username_to_add:
        return jsonify(message="Username of user to add is required"), 400

    db = next(get_db())
    try:
        space = db.query(FriendSpace).filter(FriendSpace.id == space_id).first()
        if not space:
            return jsonify(message="Friend space not found"), 404

        # Authorization: Ensure current_user_id is the owner_id of the space
        if space.owner_id != current_user_id:
            return jsonify(message="Access denied: Only the space owner can add members"), 403

        user_to_add = db.query(User).filter(User.username == username_to_add).first()
        if not user_to_add:
            return jsonify(message=f"User '{username_to_add}' not found"), 404
        
        if user_to_add.id == current_user_id: # Owner is already a member
            return jsonify(message="Owner is already a member of the space."), 409


        # Friendship Check: Verify owner and user_to_add are friends
        friendship = db.query(Friendship).filter(
            Friendship.status == "accepted",
            or_(
                and_(Friendship.requester_id == current_user_id, Friendship.receiver_id == user_to_add.id),
                and_(Friendship.requester_id == user_to_add.id, Friendship.receiver_id == current_user_id)
            )
        ).first()
        if not friendship:
            return jsonify(message="Owner must be friends with the user to add them to the space."), 403

        # Check if user is already a member
        existing_member = db.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == space_id,
            FriendSpaceMember.user_id == user_to_add.id
        ).first()
        if existing_member:
            return jsonify(message=f"User '{username_to_add}' is already a member of this space"), 409

        new_member = FriendSpaceMember(
            space_id=space_id,
            user_id=user_to_add.id,
            role="member" # Default role
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        db.refresh(new_member.user) # Ensure user details are loaded for to_dict

        return jsonify(message="Member added to space", member=new_member.to_dict()), 201
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error adding member to space: {e}")
        return jsonify(message="Error adding member to space"), 500
    finally:
        db.close()

@app.route('/api/spaces/<int:space_id>/members', methods=['GET'])
@jwt_required()
def list_members_of_friend_space(space_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        space = db.query(FriendSpace).filter(FriendSpace.id == space_id).first()
        if not space:
            return jsonify(message="Friend space not found"), 404

        # Authorization: Ensure current_user_id is a member of the space
        is_member = db.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == space_id,
            FriendSpaceMember.user_id == current_user_id
        ).first()
        if not is_member:
            return jsonify(message="Access denied: You are not a member of this space"), 403

        # Get members from space.members (already loaded if using options in query, or lazy-loaded)
        # Explicitly load user details for each member for serialization
        members = db.query(FriendSpaceMember).options(joinedload(FriendSpaceMember.user)).filter(FriendSpaceMember.space_id == space_id).all()
        serialized_members = [member.to_dict(include_space_details=False) for member in members]
        
        return jsonify(members=serialized_members), 200
    except Exception as e:
        app.logger.error(f"Error listing space members: {e}")
        return jsonify(message="Error listing space members"), 500
    finally:
        db.close()

@app.route('/api/spaces/<int:space_id>/members/<int:member_user_id>', methods=['DELETE'])
@jwt_required()
def remove_member_from_friend_space(space_id, member_user_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        space = db.query(FriendSpace).filter(FriendSpace.id == space_id).first()
        if not space:
            return jsonify(message="Friend space not found"), 404

        member_to_remove_record = db.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == space_id,
            FriendSpaceMember.user_id == member_user_id
        ).first()

        if not member_to_remove_record:
            return jsonify(message="Member not found in this space"), 404

        # Authorization:
        # 1. Current user is the owner of the space
        # OR
        # 2. Current user is the member_user_id themselves (leaving the space)
        is_owner = (space.owner_id == current_user_id)
        is_self_removal = (current_user_id == member_user_id)

        if not (is_owner or is_self_removal):
            return jsonify(message="Access denied: You do not have permission to remove this member."), 403

        # Prevent owner from being removed by themselves via this endpoint (owner should delete space or transfer ownership)
        if is_owner and member_user_id == space.owner_id:
             # This check is implicitly handled if owner role is 'owner' and we prevent removing 'owner' role.
             # For now, if owner is trying to remove themselves as a 'member' (which shouldn't happen if roles are strict)
            return jsonify(message="Owner cannot be removed from the space via this endpoint. Consider deleting the space or transferring ownership."), 403
        
        # If owner is removing another member, it's fine.
        # If user is removing themselves, it's fine (even if they are the owner, but caught by above).

        db.delete(member_to_remove_record)
        db.commit()
        return jsonify(message="Member removed from space successfully"), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error removing member from space: {e}")
        return jsonify(message="Error removing member from space"), 500
    finally:
        db.close()

# Tag API Endpoints

@app.route('/api/tags', methods=['POST'])
@jwt_required()
def create_tag():
    current_user_id = get_jwt_identity() # For potential future auditing, not strictly for auth on tag creation now
    data = request.json
    name = data.get('name')

    if not name:
        return jsonify(message="Tag name is required"), 400
    
    name = name.strip().lower() # Normalize tag name
    if not name: # Check again after stripping
        return jsonify(message="Tag name cannot be empty"), 400


    db = next(get_db())
    try:
        existing_tag = db.query(Tag).filter(Tag.name == name).first()
        if existing_tag:
            return jsonify(message="Tag already exists", tag=existing_tag.to_dict()), 409

        new_tag = Tag(name=name)
        db.add(new_tag)
        db.commit()
        db.refresh(new_tag)
        return jsonify(message="Tag created successfully", tag=new_tag.to_dict()), 201
    except sqlalchemy_exc.IntegrityError: # Handles potential race condition if unique constraint is violated
        db.rollback()
        existing_tag = db.query(Tag).filter(Tag.name == name).first()
        if existing_tag:
             return jsonify(message="Tag already exists (race condition)", tag=existing_tag.to_dict()), 409
        else: # Should not happen if constraint is on name
             app.logger.error(f"IntegrityError on tag creation for name {name} but tag not found after rollback.")
             return jsonify(message="Error creating tag due to integrity issue"), 500
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error creating tag: {e}")
        return jsonify(message="Error creating tag"), 500
    finally:
        db.close()

@app.route('/api/tags', methods=['GET'])
@jwt_required() # Or remove for public listing
def list_tags():
    db = next(get_db())
    try:
        tags = db.query(Tag).order_by(Tag.name).all()
        serialized_tags = [tag.to_dict() for tag in tags]
        return jsonify(tags=serialized_tags), 200
    except Exception as e:
        app.logger.error(f"Error listing tags: {e}")
        return jsonify(message="Error listing tags"), 500
    finally:
        db.close()

# Task-Tag Association Endpoints

def user_can_modify_task(db_session, user_id, task_id):
    """
    Helper function to check if a user has permission to modify a task (including its tags).
    Permissions:
    - Task creator.
    - If task is in a space: Space owner.
    - (Future: Space admin or specific task assignment role).
    """
    task_to_check = db_session.query(Task).options(joinedload(Task.space)).filter(Task.id == task_id).first()
    if not task_to_check:
        return False, "Task not found", 404

    if task_to_check.created_by_user_id == user_id:
        return True, "User is task creator", 200
    
    if task_to_check.space_id:
        # Ensure space relationship is loaded if not already
        if not task_to_check.space: # Should be loaded by options(joinedload(Task.space))
            db_session.refresh(task_to_check, ['space'])

        if task_to_check.space and task_to_check.space.owner_id == user_id:
            return True, "User is space owner", 200
        
        # More granular space member checks could go here if needed
        # For now, only creator or space owner.
        # is_member = db_session.query(FriendSpaceMember).filter(
        #     FriendSpaceMember.space_id == task_to_check.space_id,
        #     FriendSpaceMember.user_id == user_id
        # ).first()
        # if is_member:
        #     return True, "User is a member of the space", 200 # Or specific role check

    return False, "User does not have permission to modify this task", 403


@app.route('/api/tasks/<int:task_id>/tags', methods=['POST'])
@jwt_required()
def add_tag_to_task(task_id):
    current_user_id = get_jwt_identity()
    data = request.json
    tag_name = data.get('tag_name') # Prioritize tag_name for simplicity, can also support tag_id
    tag_id = data.get('tag_id')

    if not tag_name and not tag_id:
        return jsonify(message="tag_name or tag_id is required"), 400

    db = next(get_db())
    try:
        # Authorization check
        can_modify, reason, status_code = user_can_modify_task(db, current_user_id, task_id)
        if not can_modify:
            return jsonify(message=reason), status_code
        
        task = db.query(Task).filter(Task.id == task_id).first() # Already fetched in user_can_modify_task, but re-fetch for safety or pass object
        if not task: # Should be caught by user_can_modify_task, but good practice
            return jsonify(message="Task not found"), 404

        target_tag = None
        if tag_id:
            target_tag = db.query(Tag).filter(Tag.id == tag_id).first()
            if not target_tag:
                 return jsonify(message=f"Tag with ID {tag_id} not found"), 404
        elif tag_name:
            normalized_tag_name = tag_name.strip().lower()
            if not normalized_tag_name:
                 return jsonify(message="Tag name cannot be empty"), 400
            target_tag = db.query(Tag).filter(Tag.name == normalized_tag_name).first()
            if not target_tag: # Create tag if it doesn't exist
                target_tag = Tag(name=normalized_tag_name)
                db.add(target_tag)
                db.flush() # To get target_tag.id before commit for TaskTag, or commit and then create TaskTag

        if not target_tag: # Should not be reachable if logic above is correct
            return jsonify(message="Tag not found or created"), 404
            
        # Check if association already exists
        existing_association = db.query(TaskTag).filter(
            TaskTag.task_id == task_id,
            TaskTag.tag_id == target_tag.id
        ).first()
        if existing_association:
            return jsonify(message="Tag already associated with this task", tag=target_tag.to_dict()), 409

        new_association = TaskTag(task_id=task_id, tag_id=target_tag.id)
        db.add(new_association)
        db.commit()
        
        # Refresh task to get updated tags list for response
        db.refresh(task)
        return jsonify(message="Tag added to task", task=task.to_dict()), 201

    except Exception as e:
        db.rollback()
        app.logger.error(f"Error adding tag to task: {e}")
        return jsonify(message="Error adding tag to task"), 500
    finally:
        db.close()

@app.route('/api/tasks/<int:task_id>/tags/<int:tag_id_to_remove>', methods=['DELETE'])
@jwt_required()
def remove_tag_from_task(task_id, tag_id_to_remove):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        # Authorization check
        can_modify, reason, status_code = user_can_modify_task(db, current_user_id, task_id)
        if not can_modify:
            return jsonify(message=reason), status_code
        
        task = db.query(Task).filter(Task.id == task_id).first() # Re-fetch or pass object
        if not task:
            return jsonify(message="Task not found"), 404

        association_to_delete = db.query(TaskTag).filter(
            TaskTag.task_id == task_id,
            TaskTag.tag_id == tag_id_to_remove
        ).first()

        if not association_to_delete:
            return jsonify(message="Tag not associated with this task or tag not found"), 404

        db.delete(association_to_delete)
        db.commit()
        
        db.refresh(task) # Refresh task to get updated tags list for response
        return jsonify(message="Tag removed from task", task=task.to_dict()), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error removing tag from task: {e}")
        return jsonify(message="Error removing tag from task"), 500
    finally:
        db.close()

# Helper function for Task Assignment Authorization
def check_task_assignment_permission(db_session, task, assigner_id, assignee_id):
    """
    Checks if the assigner_id has permission to assign/unassign the task to/from assignee_id.
    Returns: (bool, message, status_code)
    """
    if not task:
        return False, "Task not found", 404

    is_task_creator = (task.created_by_user_id == assigner_id)
    is_space_owner = False
    assigner_is_member_of_space = False
    assignee_is_member_of_space = False

    if task.space_id:
        space = db_session.query(FriendSpace).filter(FriendSpace.id == task.space_id).first()
        if not space: # Should not happen if DB is consistent
            return False, "Task's associated space not found", 500
        
        is_space_owner = (space.owner_id == assigner_id)

        assigner_membership = db_session.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == task.space_id,
            FriendSpaceMember.user_id == assigner_id
        ).first()
        assigner_is_member_of_space = assigner_membership is not None

        assignee_membership = db_session.query(FriendSpaceMember).filter(
            FriendSpaceMember.space_id == task.space_id,
            FriendSpaceMember.user_id == assignee_id
        ).first()
        assignee_is_member_of_space = assignee_membership is not None

    # --- Personal Task Logic ---
    if not task.space_id:
        if not is_task_creator:
            return False, "Only the task creator can assign/unassign personal tasks.", 403
        
        # For personal tasks, creator can assign to self or friends
        if assigner_id != assignee_id: # Not self-assigning
            are_friends = db_session.query(Friendship).filter(
                Friendship.status == "accepted",
                or_(
                    and_(Friendship.requester_id == assigner_id, Friendship.receiver_id == assignee_id),
                    and_(Friendship.requester_id == assignee_id, Friendship.receiver_id == assigner_id)
                )
            ).first()
            if not are_friends:
                return False, "Personal tasks can only be assigned to self or friends.", 403
        return True, "Permission granted for personal task.", 200

    # --- Space Task Logic ---
    else: # Task is in a space
        # Assigner must be task creator or space owner
        if not (is_task_creator or is_space_owner):
            return False, "Only the task creator or space owner can assign/unassign tasks in this space.", 403
        
        # Assignee must be a member of the space
        if not assignee_is_member_of_space:
            return False, "Cannot assign task: target user is not a member of this space.", 403
        
        return True, "Permission granted for space task.", 200


# Task Assignment API Endpoints

@app.route('/api/tasks/<int:task_id>/assign', methods=['POST'])
@jwt_required()
def assign_task(task_id):
    current_user_id = get_jwt_identity()
    data = request.json
    assign_to_user_id = data.get('assign_to_user_id')

    if assign_to_user_id is None: # Check for None explicitly, as 0 is a valid user_id
        return jsonify(message="assign_to_user_id is required"), 400

    db = next(get_db())
    try:
        task_to_assign = db.query(Task).options(joinedload(Task.space)).filter(Task.id == task_id).first() # Load space for permission check
        if not task_to_assign:
            return jsonify(message="Task not found"), 404

        user_to_assign = db.query(User).filter(User.id == assign_to_user_id).first()
        if not user_to_assign:
            return jsonify(message="User to assign not found"), 404

        # Authorization
        can_assign, reason, status_code = check_task_assignment_permission(db, task_to_assign, current_user_id, assign_to_user_id)
        if not can_assign:
            return jsonify(message=reason), status_code

        # Check if already assigned
        existing_assignment = db.query(TaskAssignment).filter(
            TaskAssignment.task_id == task_id,
            TaskAssignment.assigned_to_user_id == assign_to_user_id
        ).first()
        if existing_assignment:
            return jsonify(message="Task already assigned to this user", assignment=existing_assignment.to_dict()), 409

        new_assignment = TaskAssignment(
            task_id=task_id,
            assigned_to_user_id=assign_to_user_id
        )
        db.add(new_assignment)
        db.commit()
        db.refresh(new_assignment)
        
        # Refresh task to include new assignee in response
        db.refresh(task_to_assign) 
        return jsonify(message="Task assigned successfully", task=task_to_assign.to_dict()), 201

    except Exception as e:
        db.rollback()
        app.logger.error(f"Error assigning task: {e}")
        return jsonify(message="Error assigning task"), 500
    finally:
        db.close()

@app.route('/api/tasks/<int:task_id>/assignments/<int:assigned_user_id>', methods=['DELETE'])
@jwt_required()
def unassign_task(task_id, assigned_user_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        task_to_unassign_from = db.query(Task).options(joinedload(Task.space)).filter(Task.id == task_id).first()
        if not task_to_unassign_from:
            return jsonify(message="Task not found"), 404

        # Authorization: current_user_id (acting user) needs permission relative to assigned_user_id (target of unassignment)
        # The permission logic for unassigning can be similar to assigning, or slightly different if self-unassignment is always allowed.
        
        # If current_user is the one assigned, they can always unassign themselves.
        if current_user_id == assigned_user_id:
            pass # Self-unassignment, allow
        else:
            # Otherwise, check if current_user has general assignment rights for this task & user
            can_unassign, reason, status_code = check_task_assignment_permission(db, task_to_unassign_from, current_user_id, assigned_user_id)
            if not can_unassign:
                return jsonify(message=reason), status_code
        
        assignment_to_delete = db.query(TaskAssignment).filter(
            TaskAssignment.task_id == task_id,
            TaskAssignment.assigned_to_user_id == assigned_user_id
        ).first()

        if not assignment_to_delete:
            return jsonify(message="Task assignment not found for this user"), 404

        db.delete(assignment_to_delete)
        db.commit()
        
        db.refresh(task_to_unassign_from) # Refresh task to reflect unassignment
        return jsonify(message="Task unassigned successfully", task=task_to_unassign_from.to_dict()), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error unassigning task: {e}")
        return jsonify(message="Error unassigning task"), 500
    finally:
        db.close()

@app.route('/api/tasks/assigned_to_me', methods=['GET'])
@jwt_required()
def list_tasks_assigned_to_me():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        assignments = db.query(TaskAssignment).filter(
            TaskAssignment.assigned_to_user_id == current_user_id
        ).options(joinedload(TaskAssignment.task).joinedload(Task.created_by), 
                  joinedload(TaskAssignment.task).joinedload(Task.space),
                  joinedload(TaskAssignment.task).joinedload(Task.task_tag_associations).joinedload(TaskTag.tag), # Eager load tags for tasks
                  joinedload(TaskAssignment.task).joinedload(Task.assignees).joinedload(TaskAssignment.assigned_to) # Eager load other assignees for tasks
                  ).all()
        
        # Serialize tasks directly from the assignment's task relationship
        serialized_tasks = [assignment.task.to_dict() for assignment in assignments if assignment.task]
        
        return jsonify(tasks=serialized_tasks), 200
    except Exception as e:
        app.logger.error(f"Error listing tasks assigned to me: {e}")
        return jsonify(message="Error listing tasks assigned to me"), 500
    finally:
        db.close()

# Reminder CRUD Endpoints
@app.route('/api/reminders', methods=['POST'])
@jwt_required()
def create_reminder():
    current_user_id = get_jwt_identity()
    data = request.json
    title = data.get('title')
    content = data.get('content')
    due_date_str = data.get('due_date')

    if not title:
        return jsonify(message="Title is required"), 400

    parsed_due_date = None
    if due_date_str:
        try:
            # Attempt to parse with time first, then date only
            if 'T' in due_date_str:
                parsed_due_date = datetime.fromisoformat(due_date_str)
            else:
                parsed_due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify(message="Invalid due_date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"), 400

    db = next(get_db())
    try:
        new_reminder = Reminder(
            title=title,
            content=content,
            due_date=parsed_due_date,
            user_id=current_user_id
        )
        db.add(new_reminder)
        db.commit()
        db.refresh(new_reminder)
        return jsonify(message="Reminder created", reminder=new_reminder.to_dict()), 201
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error creating reminder: {e}")
        return jsonify(message="Error creating reminder"), 500
    finally:
        db.close()

@app.route('/api/reminders', methods=['GET'])
@jwt_required()
def list_reminders():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        reminders = db.query(Reminder).filter(Reminder.user_id == current_user_id).all()
        serialized_reminders = [r.to_dict() for r in reminders]
        return jsonify(reminders=serialized_reminders), 200
    except Exception as e:
        app.logger.error(f"Error listing reminders: {e}")
        return jsonify(message="Error listing reminders"), 500
    finally:
        db.close()

@app.route('/api/reminders/<int:reminder_id>', methods=['GET'])
@jwt_required()
def get_reminder(reminder_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user_id).first()
        if not reminder:
            return jsonify(message="Reminder not found or access denied"), 404
        return jsonify(reminder=reminder.to_dict()), 200
    except Exception as e:
        app.logger.error(f"Error getting reminder: {e}")
        return jsonify(message="Error getting reminder"), 500
    finally:
        db.close()

@app.route('/api/reminders/<int:reminder_id>', methods=['PUT'])
@jwt_required()
def update_reminder(reminder_id):
    current_user_id = get_jwt_identity()
    data = request.json
    db = next(get_db())
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user_id).first()
        if not reminder:
            return jsonify(message="Reminder not found or access denied"), 404

        if 'title' in data:
            reminder.title = data['title']
        if 'content' in data:
            reminder.content = data['content']
        if 'is_completed' in data:
            reminder.is_completed = data['is_completed']
        if 'due_date' in data:
            due_date_str = data.get('due_date')
            if due_date_str:
                try:
                    if 'T' in due_date_str:
                        reminder.due_date = datetime.fromisoformat(due_date_str)
                    else:
                        reminder.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                except ValueError:
                    return jsonify(message="Invalid due_date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"), 400
            else:
                reminder.due_date = None # Allow clearing the due date

        db.commit()
        db.refresh(reminder)
        return jsonify(message="Reminder updated", reminder=reminder.to_dict()), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error updating reminder: {e}")
        return jsonify(message="Error updating reminder"), 500
    finally:
        db.close()

@app.route('/api/reminders/<int:reminder_id>', methods=['DELETE'])
@jwt_required()
def delete_reminder(reminder_id):
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == current_user_id).first()
        if not reminder:
            return jsonify(message="Reminder not found or access denied"), 404

        db.delete(reminder)
        db.commit()
        return jsonify(message="Reminder deleted"), 200
    except Exception as e:
        db.rollback()
        app.logger.error(f"Error deleting reminder: {e}")
        return jsonify(message="Error deleting reminder"), 500
    finally:
        db.close()

@app.route('/api/users/login', methods=['POST'])
def login_user():
    data = request.json
    username_or_email = data.get('username_or_email') # Allow login with username or email
    password = data.get('password')

    if not username_or_email or not password:
        return jsonify(message="Username/email and password are required"), 400

    db = next(get_db())
    try:
        user = db.query(User).filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if not user or not verify_password(password, user.password_hash):
            return jsonify(message="Invalid credentials"), 401

        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token), 200
    except Exception as e:
        app.logger.error(f"Error during login: {e}")
        return jsonify(message="Error during login"), 500
    finally:
        db.close()

@app.route('/api/users/logout', methods=['POST'])
@jwt_required()
def logout_user():
    # For JWT, logout is typically handled client-side by deleting the token.
    # Server-side blocklisting can be implemented for more robust logout.
    return jsonify(message="Logout successful"), 200

@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == current_user_id).first()
        if not user:
            return jsonify(message="User not found"), 404 # Should not happen if token is valid
        return jsonify(logged_in_as={"id": user.id, "username": user.username}), 200
    except Exception as e:
        app.logger.error(f"Error in protected route: {e}")
        return jsonify(message="Error fetching user data"), 500
    finally:
        db.close()
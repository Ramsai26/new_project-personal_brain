from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from src.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reminders = relationship("Reminder", back_populates="owner")

class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    content = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="reminders")
    # Relationship to access shared instances of this reminder
    shares = relationship("SharedReminder", back_populates="reminder", cascade="all, delete-orphan")


    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_completed": self.is_completed,
            "user_id": self.user_id
        }

class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False) # User who sent the request
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who received the request
    status = Column(String, default="pending", nullable=False)  # "pending", "accepted", "rejected"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requester_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

    __table_args__ = (UniqueConstraint('requester_id', 'receiver_id', name='uq_friendship_pair'),)

    def to_dict(self):
        return {
            "id": self.id,
            "requester_id": self.requester_id,
            "requester_username": self.requester.username if self.requester else None,
            "receiver_id": self.receiver_id,
            "receiver_username": self.receiver.username if self.receiver else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class SharedReminder(Base):
    __tablename__ = "shared_reminders"

    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False)
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # User who owns and shared the reminder
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # User with whom the reminder is shared
    shared_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active") # e.g., "active", "revoked"

    reminder = relationship("Reminder", back_populates="shares")
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])
    shared_with = relationship("User", foreign_keys=[shared_with_user_id])

    __table_args__ = (UniqueConstraint('reminder_id', 'shared_with_user_id', name='uq_shared_reminder_to_user'),)

    def to_dict(self):
        return {
            "id": self.id,
            "reminder_id": self.reminder_id,
            "reminder_details": self.reminder.to_dict() if self.reminder else None,
            "shared_by_user_id": self.shared_by_user_id,
            "shared_by_username": self.shared_by.username if self.shared_by else None,
            "shared_with_user_id": self.shared_with_user_id,
            "shared_with_username": self.shared_with.username if self.shared_with else None,
            "shared_at": self.shared_at.isoformat() if self.shared_at else None,
            "status": self.status,
        }

class FriendSpace(Base):
    __tablename__ = "friend_spaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

    owner = relationship("User")
    members = relationship("FriendSpaceMember", back_populates="space", cascade="all, delete-orphan")

    def to_dict(self, include_members=False):
        data = {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "owner_username": self.owner.username if self.owner else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "description": self.description,
            "member_count": len(self.members) if self.members else 0
        }
        if include_members:
            data["members"] = [member.to_dict(include_space_details=False) for member in self.members]
        return data

class FriendSpaceMember(Base):
    __tablename__ = "friend_space_members"

    id = Column(Integer, primary_key=True, index=True)
    space_id = Column(Integer, ForeignKey("friend_spaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    role = Column(String, default="member", nullable=False)  # e.g., "member", "admin"

    space = relationship("FriendSpace", back_populates="members")
    user = relationship("User")

    __table_args__ = (UniqueConstraint('space_id', 'user_id', name='uq_space_user'),)

    def to_dict(self, include_user_details=True, include_space_details=True):
        data = {
            "id": self.id,
            "role": self.role,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
        }
        if include_user_details and self.user:
            data["user_id"] = self.user.id
            data["username"] = self.user.username
        if include_space_details and self.space:
            data["space_id"] = self.space.id
            data["space_name"] = self.space.name
        return data

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    status = Column(String, default="todo", nullable=False, index=True)  # "todo", "in_progress", "done", "archived"
    priority = Column(String, default="medium", nullable=False)  # "low", "medium", "high"
    due_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    space_id = Column(Integer, ForeignKey("friend_spaces.id"), nullable=True) # Task can be personal or for a space

    created_by = relationship("User")
    space = relationship("FriendSpace")
    
    task_tag_associations = relationship("TaskTag", back_populates="task", cascade="all, delete-orphan", lazy="selectin")
    assignees = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by_user_id": self.created_by_user_id,
            "created_by_username": self.created_by.username if self.created_by else None,
            "space_id": self.space_id,
            "space_name": self.space.name if self.space else None,
            "tags": [assoc.tag.to_dict() for assoc in self.task_tag_associations],
            "assignees": [assignment.to_dict() for assignment in self.assignees]
        }

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task_tag_associations = relationship("TaskTag", back_populates="tag", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class TaskTag(Base):
    __tablename__ = "task_tags"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('task_id', 'tag_id', name='uq_task_tag'),)

    task = relationship("Task", back_populates="task_tag_associations")
    tag = relationship("Tag", back_populates="task_tag_associations")

class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('task_id', 'assigned_to_user_id', name='uq_task_assignee'),)

    task = relationship("Task", back_populates="assignees")
    assigned_to = relationship("User") # Eager load user details if frequently accessed

    def to_dict(self):
        return {
            "id": self.id, # Include the ID of the assignment itself
            "task_id": self.task_id,
            "assigned_to_user_id": self.assigned_to_user_id,
            "assigned_to_username": self.assigned_to.username if self.assigned_to else None,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None
        }

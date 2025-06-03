from flask_sqlalchemy import SQLAlchemy

from datetime import datetime
db = SQLAlchemy()


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(250), nullable=False)
    priority = db.Column(db.Integer, default=2, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    remind_at = db.Column(db.DateTime, nullable=True)
    is_reminded = db.Column(db.Boolean, default=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    follow_up_sent = db.Column(db.Boolean, default=False)
    follow_up_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True, index=True)

    pomodoro_sessions = db.relationship(
        'PomodoroSession',
        back_populates='task',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Task {self.id}: {self.description}>'


class PomodoroSession(db.Model):
    __tablename__ = 'pomodoro_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    session_type = db.Column(db.String(15), nullable=False)
    status = db.Column(db.String(15), default='started', nullable=False)

    task = db.relationship('Task', back_populates='pomodoro_sessions')

    def __repr__(self):
        return (f'<PomodoroSession {self.id} user '
                f'{self.user_id} - {self.session_type} ({self.status})>')


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False, index=True)
    entry_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    tags_str = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (f"<JournalEntry {self.id} (User: {self.user_id}, "
                f"Type: {self.entry_type})>")


class MoodEntry(db.Model):
    __tablename__ = 'mood_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=True)
    text = db.Column(db.Text, nullable=True)
    tags_str = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<MoodEntry {self.id} (User: {self.user_id}, Rating: {self.rating})>"

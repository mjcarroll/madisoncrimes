from app import app, db

import os
import enum

inc_association_table = db.Table(
    'incident_to_record',
    db.Column('record_id', db.Integer, db.ForeignKey('record.id'), primary_key=True),
    db.Column('incident_id', db.Integer, db.ForeignKey('incident.id'), primary_key=True),
)

class RecordType(enum.Enum):
    arrest = 1
    incident = 2

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    pages = db.Column(db.Integer)
    on_madison = db.Column(db.Boolean, nullable=False, default=False)
    downloaded = db.Column(db.Boolean, nullable=False, default=False)
    converted = db.Column(db.Boolean, nullable=False, default=False)
    inserted = db.Column(db.Boolean, nullable=False, default=False)
    report_type = db.Column(db.Enum(RecordType))
    report_text = db.Column(db.Text)

    def content_path(self):
        return os.path.join(app.config['DATA_DIR'], 'reports', str(self.id))

    def is_downloaded(self):
        return os.path.exists(self.conent_path())

    @property
    def serialize(self):
        if self.report_type == RecordType.arrest:
            t = 'arrest'
        elif self.report_type == RecordType.incident:
            t = 'incident'
        return {
           'id'         : self.id,
           'start_date' : self.start_date,
           'end_date'   : self.end_date,
           'pages'      : self.pages,
           'on_madison' : self.on_madison,
           'downloaded' : self.downloaded,
           'converted'  : self.converted,
           'inserted'   : self.inserted,
           'report_type': t
        }

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(250), nullable=False, unique=True)
    needs_moderation = db.Column(db.Boolean, nullable=False, default=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    address = db.Column(db.String(500))
    raw = db.Column(db.String(10000))

    def __repr__(self):
        return '<Location: id=%d location=%s>' % (self.id, self.location)

    @property
    def serialize(self):
        return {
            'id': self.id,
            'location': self.location,
            'needs_moderation': self.needs_moderation,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address
        }

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident = db.Column(db.String(250), nullable=False)

    def __repr__(self):
        return '<Incident: id=%d incident=%s>' % (self.id, self.incident)

    @property
    def serialize(self):
        return {
            'id': self.id,
            'incident': self.incident
        }

class Record(db.Model):
    __table_args__ = (db.UniqueConstraint('case_yr', 'case_id', name='_case_uc'),)

    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.Enum(RecordType))

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=True)

    case_yr = db.Column(db.Integer)
    case_id = db.Column(db.Integer)

    report_id = db.Column(db.Integer, db.ForeignKey('report.id')) 
    report = db.relationship(Report)

    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    location = db.relationship(Location)
    incidents = db.relationship('Incident', 
        secondary=inc_association_table, 
        lazy='subquery',
        backref=db.backref('incidents', lazy=True))

    shift = db.Column(db.Integer)

    person = db.Column(db.String(255))
    person_res = db.Column(db.String(255))

    def __repr__(self):
        return '''<Record: {self.case_yr:02d}-{self.case_id:06d} 
            type={self.incident_type}
            report={self.report.id}
            date={self.date}
            time={self.time}
            shift={self.shift}
            location={self.location}>'''.format(**locals())

    @property
    def serialize(self):
        if self.incident_type == RecordType.arrest:
            t = 'arrest'
        elif self.incident_type == RecordType.incident:
            t = 'incident'

        return {
           'id'         : self.id,
           'case'       : '{:02d}-{:06d}'.format(self.case_yr, self.case_id),
           'incident_type': t,
           'report_id': self.report_id,
           'date': str(self.date),
           'time': str(self.time),
           'shift': self.shift,
           'location': self.location.serialize,
           'incidents': [i.serialize for i in self.incidents]
        }

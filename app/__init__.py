from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

import click
import re
import datetime

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models, utils 

def sync_reports_from_madison():
    models.Report.query.filter(models.Report.on_madison == True).update({'on_madison': False})
    db.session.commit()
    arrest_reports = utils.list_madison_arrests()
    for report in arrest_reports:
        existing = models.Report.query.filter_by(id=report).first()
        if existing is None:
            r = models.Report()
            r.id = int(report)
            r.downloaded = utils.is_downloaded(report) 
            r.on_madison = True
            r.report_type = models.RecordType.arrest
            db.session.add(r)
        else:
            existing.downloaded = utils.is_downloaded(report)
            existing.on_madison = True
        db.session.commit()

    incident_reports = utils.list_madison_incidents()
    for report in incident_reports:
        existing = models.Report.query.filter_by(id=report).first()
        if existing is None:
            r = models.Report()
            r.id = int(report)
            r.downloaded = utils.is_downloaded(report) 
            r.on_madison = True
            r.report_type = models.RecordType.incident
            db.session.add(r)
        else:
            existing.downloaded = utils.is_downloaded(report)
            existing.on_madison = True
        db.session.commit()

def download_reports_from_madison():
    reports = models.Report.query.all()
    for report in reports:
        if report.on_madison and not report.downloaded:
            print('Importing report report (web): ', report)
            utils.download_report(str(report.id))

def import_reports_from_disk():
    import os, shutil
    arrest_reports = os.listdir(os.path.join(app.config['DATA_DIR'], 
                                              'arrests'))
    for report in arrest_reports:
        existing = models.Report.query.filter_by(id=report).first()
        if existing is None:
            print('Importing arrest report (disk): ', report)
            r = models.Report()
            r.id = int(report)
            r.downloaded = True 
            r.report_type = models.RecordType.arrest
            db.session.add(r)
            db.session.commit()
        shutil.copyfile(os.path.join(app.config['DATA_DIR'], 'arrests', report),
                        os.path.join(app.config['DATA_DIR'], 'reports', report))
    
    incident_reports = os.listdir(os.path.join(app.config['DATA_DIR'],
                                              'incidents'))
    for report in incident_reports:
        existing = models.Report.query.filter_by(id=report).first()
        if existing is None:
            print('Importing incident report (disk): ', report)
            r = models.Report()
            r.id = int(report)
            r.downloaded = True 
            r.report_type = models.RecordType.incident
            db.session.add(r)
            db.session.commit()
        shutil.copyfile(os.path.join(app.config['DATA_DIR'], 'incidents', report),
                        os.path.join(app.config['DATA_DIR'], 'reports', report))

@app.cli.command('sync')
def sync():
    import_reports_from_disk()
    sync_reports_from_madison()
    download_reports_from_madison()

    arrests = models.Report.query.filter(models.Report.report_type == models.RecordType.arrest)
    incidents = models.Report.query.filter(models.Report.report_type == models.RecordType.incident)

    print('Found arrest reports: {}'.format(arrests.count()))
    print('Found incident reports: {}'.format(incidents.count()))

@app.cli.command('convert_to_txt')
def convert_to_txt():
    import subprocess
    import os
    reports = models.Report.query.filter_by(downloaded=True)
    for report in reports:
        print('Converting report: ', report.id)

        if report.report_type == models.RecordType.incident:
            txt = subprocess.check_output(['pdftotext', 
                                           '-nopgbrk', 
                                           '-layout', 
                                           report.content_path(), '-'])
        elif report.report_type == models.RecordType.arrest:
            txt = subprocess.check_output(['pdftotext', 
                                           '-nopgbrk', 
                                           report.content_path(), '-'])
        report.report_text = txt
        report.converted = True
        db.session.commit()

def add_or_create_location(address):
    location = models.Location.query.filter_by(location=address).first()
    if not location:
        location = models.Location(location=address)
    return location

def add_or_create_incident(text):
    incident = models.Incident.query.filter_by(incident=text).first()
    if not incident:
        incident = models.Incident(incident=text)
    return incident

def parse_incident(report, record):
    case = record['Case'].split('-')
    if case[0] == '' and case[1] == '':
        return

    case_yr = int(case[0][1:])
    case_id = int(case[1])

    existing = models.Record.query.filter_by(case_id=case_id, case_yr=case_yr).first()

    if existing is not None:
        r = existing
    else:
        r = models.Record()

    r.case_yr = case_yr
    r.case_id = case_id
    r.date = record['DateTime'].date()
    r.time = record['DateTime'].time()
    r.incident_type = models.RecordType.incident
    r.report = report
    r.location = add_or_create_location(record['Address'])
    r.shift = {'I': 1, 'II': 2, 'III': 3}[record['Shift']]
    r.incidents = []
    r.person = None
    r.person_res = None


    for inc in record['Incident']:
        incident = add_or_create_incident(inc)
        r.incidents.append(incident)

    if not existing:
        db.session.add(r)

def parse_arrest(report, record):
    case = record['Case'].split('-')
    case_yr = int(case[0])
    case_id = int(case[1])

    existing = models.Record.query.filter_by(case_id=case_id, case_yr=case_yr).first()
    if existing is not None:
        r = existing
    else:
        r = models.Record()

    r.case_yr = case_yr
    r.case_id = case_id
    r.date = record['Date']
    r.time = None
    r.incident_type = models.RecordType.arrest
    r.report = report
    r.location = add_or_create_location(record['Location'])
    r.incidents = []
    r.person = record['Name']
    r.person_res = record['Res']
    r.shift = 0
    for inc in record['Incident']:
        incident = add_or_create_incident(inc)
        r.incidents.append(incident)
    if not existing:
        db.session.add(r)


@app.cli.command('parse')
def parse():
    reports = models.Report.query.filter_by(downloaded=True,
                                            converted=True,
                                            inserted=False)

    for report in reports:
        print('Parsing report: ', report)
        lines = report.report_text.decode().split('\n')
        for line in lines:
            line = line.strip()
            matches = re.match(r'Page (\d*) of (\d*)', line)
            if matches:
                report.pages = int(matches.groups()[1])
            matches = re.match(r'\((.*) To (.*)\)', line)
            if matches:
                f = matches.groups()[0].strip()
                f = datetime.datetime.strptime(f, '%b %d, %Y')
                t = matches.groups()[1].strip()
                t = datetime.datetime.strptime(t, '%b %d, %Y')
                report.start_date = f.date()
                report.end_date = t.date()

        if report.report_type == models.RecordType.incident:
            for record in utils.extract_incidents(report):
                parse_incident(report, record)
        elif report.report_type == models.RecordType.arrest:
            for record in utils.extract_arrests(report):
                parse_arrest(report, record)
        report.inserted = True
        db.session.commit()

@app.cli.command('populate_locs')
def populate_locations():
    import json, os
    f = open(os.path.join(app.config['DATA_DIR'], 'location.json'), 'r')
    data = json.load(f)

    cached = {}
    for d in data:
        cached[d['location']] = d

    locations = models.Location.query.filter_by(needs_moderation=True)

    print(len(locations.all()), len(cached))

    for location in locations:
        if location.location in cached:
            cc = cached[location.location]
            if cc['needs_moderation'] == '0':
                location.address = cc['address']
                location.latitude = float(cc['latitude'])
                location.longitude = float(cc['longitude'])
                location.needs_moderation = False
                location.raw = cc['raw']
    db.session.commit()


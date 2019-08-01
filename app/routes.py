from app import app
from app import scrape

from app import models

from flask import jsonify, send_from_directory, Response, render_template

import os

@app.route('/reports')
def reports():
    reports = models.Report.query.all()
    return render_template('reports.html', reports=reports)

@app.route('/reports/<id>')
def report(id):
    report = models.Report.query.get_or_404(id)
    return report.report_text

@app.route('/api/reports')
def api_reports():
    reports = models.Report.query.all()
    return jsonify(data=[r.serialize for r in reports])

@app.route('/api/records')
def api_records_all():
    records = models.Record.query.order_by(models.Record.id.desc()).all()
    return jsonify(data=[r.serialize for r in records])

@app.route('/api/records/<int:page>')
def api_records(page=1):
    per_page = 100
    records = models.Record.query.order_by(models.Record.id.desc()).paginate(page, per_page)
    return jsonify(data=[r.serialize for r in records.items])

@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html', key=app.config['MAPS_API_KEY'])

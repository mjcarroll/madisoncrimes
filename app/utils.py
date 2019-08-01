#!/usr/bin/env python

from app import app

import os
import re
import datetime

from lxml import html
import requests

MADISON_URL = 'https://www.madisonal.gov/Archive.aspx'
INCIDENT_AMID = 67
ARREST_AMID = 68

def list_madison_reports(amid):
    payload = {'AMID': amid, 'Type': '', 'ADID': ''}
    page = requests.get(MADISON_URL, params=payload)
    tree = html.fromstring(page.text)
    urls = tree.xpath('//span[@class="archive"]/a')
    ret = []
    for url in urls:
        url_s = url.attrib['href']
        url_s = url_s.split('=')
        if len(url_s) < 2:
            continue
        ret.append(url_s[1])
    return ret

def list_madison_arrests():
    return list_madison_reports(ARREST_AMID)

def list_madison_incidents():
    return list_madison_reports(INCIDENT_AMID)

def download_report(fid):
    payload = {'ADID': fid}
    page = requests.get(MADISON_URL, params=payload)
    fname = os.path.join(app.config['DATA_DIR'], 'reports', fid)
    with open(fname, 'wb') as f:
        f.write(page.content)

def is_downloaded(report):
    return os.path.exists(os.path.join(app.config['DATA_DIR'], 'reports', report))

def clean_report(lines):
    keep = []
    rej = ['', '\n', 'Incident Report', 'Arrest Report', 'Madison Police Department', 'Date', 'Arrest Information', 'Arrest', 'Report Designed by the Law Enforcement Technology Coordinator']
    for line in lines:
        line = line.strip()
        if line in rej:
            continue
        if re.match(r'Page \d* of \d*', line):
            continue
        if re.match(r'\((.*) To (.*)\)', line):
            continue
        keep.append(line)
    return keep

def reformat_incident(lines):
    new_lines = []
    for line in lines:
        if line.find('Time:') > 0:
            new_lines.append(line[0:line.find('Time:')])
            line = line[line.find('Time:'):]
        if line.find('Shift:') > 0:
            new_lines.append(line[0:line.find('Shift:')])
            line = line[line.find('Shift:'):]
        if line.find('Location:') > 0:
            new_lines.append(line[0:line.find('Location:')])
            line = line[line.find('Location:'):]
        new_lines.append(line)
    new_lines = [l.strip() for l in new_lines if len(l)]
    return new_lines

def clean_incident(inc):
    inc = inc.replace('-', ' ')
    inc = inc.replace('    ', ' ')
    inc = inc.replace('   ', ' ')
    inc = inc.replace('  ', ' ')
    inc = inc.replace('1st', '1')
    inc = inc.replace('1ST', '1')
    inc = inc.replace('2nd', '2')
    inc = inc.replace('2ND', '2')
    inc = inc.replace('3rd', '3')
    inc = inc.replace('3RD', '3')
    inc = inc.replace('4th', '4')
    inc = inc.replace('4TH', '4')
    inc = inc.strip('.')
    return inc

def extract_arrests(report):
    file = str(report.id)
    lines = report.report_text.decode().split('\n')
    lines = clean_report(lines)

    records = []
    record = None
    
    date_lines = {}
    cno_lines = {}
    other_lines = {}
    
    for ii, line in enumerate(lines):
        date_match = re.match(r'(\d*)/(\d*)/(\d*)', line)
        case_match = re.match(r'(\d\d)-(\d*)', line)

        if date_match:
            date_lines[ii] = line
        elif case_match:
            cno_lines[ii] = line
        else:
            other_lines[ii] = line
            
    date_keys = sorted(date_lines.keys())
    cno_keys = sorted(cno_lines.keys())
    other_keys = sorted(other_lines.keys())
    
    for ii in range(0, len(date_keys) - 1):
        dk = date_keys[ii]
        dkn = date_keys[ii+1]
        ck = [ ck for ck in cno_keys if ck > dk and ck < dkn][0]        
        between_dk_ck = [ok for ok in other_keys if ok > dk and ok < ck]
        between_ck_dkn = [ok for ok in other_keys if ok > ck and ok < dkn]
        
        all_other = [other_lines[k] for k in between_dk_ck]
        all_other.extend([other_lines[k] for k in between_ck_dkn])
        all_other_str = ' '.join(all_other)
        
        match = re.match(r'([\w\s]*), (.*) was arrested at (.*) on the charge\(s\) of:', all_other_str)
        if match:
            end = match.end()
            g = 0
            for ii, ao in enumerate(all_other):
                if end >= len(ao):
                    end = end - (len(ao) + 1)
                else:
                    g = ii
                    break
            dt = datetime.datetime.strptime(date_lines[dk],
                '%m/%d/%y')
            record = {
                'Name': match.groups()[0],
                'Date': dt,
                'Res': match.groups()[1],
                'Location': match.groups()[2],
                'Incident': [clean_incident(i) for i in all_other[g:]],
                'Case': cno_lines[ck],
                'File': file
            }
            records.append(record)
            
        else:
            continue             
    return records

def extract_incidents(report):
    file = str(report.id)
    lines = report.report_text.decode().split('\n')
    lines = clean_report(lines)
    lines = reformat_incident(lines)

    records = []
    record = None

    cno_lines = {}
    time_lines = {}
    shift_lines = {}
    date_lines = {}
    loc_lines = {}
    inc_lines = {}
    line_idx = [ cno_lines, time_lines, shift_lines, date_lines, loc_lines, inc_lines]

    case_str = "Case No.: "
    time_str = "Time: "
    shift_str = "Shift: "
    date_str = "Date Reported: "
    loc_str = "Location: "
    inc_str = "Incident: "
    strings = [ case_str, time_str, shift_str, date_str, loc_str, inc_str ]

    # Sort each line into it's own dict by line type
    for ii, line in enumerate(lines):
        for (_str, _idx) in zip(strings, line_idx):
            if line.find(_str) >= 0:
                _idx[ii] = line[line.find(_str) + len(_str):].strip()

    cno_keys = sorted(cno_lines.keys())
    cno_keys_s = cno_keys[1:] + [1e6]

    for key, key_plus in zip(cno_keys, cno_keys_s):
        time = [v for (k,v) in time_lines.items() if
                    k > key and k < key_plus]
        date = [v for (k,v) in date_lines.items() if
                    k > key and k < key_plus]
        shift = [v for (k,v) in shift_lines.items() if
                    k > key and k < key_plus]
        loc = [v for (k,v) in loc_lines.items() if
                    k > key and k < key_plus]
        incs = [v for (k,v) in inc_lines.items() if
                    k > key and k < key_plus]

        record = {}
        if file:
            record['File'] = file
        record['Case'] = cno_lines[key]
        dt = datetime.datetime.strptime(time[0] + ' ' + date[0],
            '%I:%M %p %B %d, %Y')

        new_incs = []
        for inc in incs:
            inc = clean_incident(inc)
            new_incs.append(inc)

        record['DateTime'] = dt
        record['Shift'] = shift[0]
        record['Address'] = loc[0]
        record['Incident'] = new_incs
        records.append(record)

    return records

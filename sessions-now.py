#!/usr/bin/env python

import sys
import datetime
import dateutil.parser
import json
import urllib.parse
import hashlib

import requests
import flask
import lxml.html

def from_url_raw(url):
    fname = f'cache/{hashlib.md5(url.encode()).hexdigest()}'
    try:
        with open(fname) as f:
            return f.read()
    except:
        t = requests.get(url).text
        with open(fname, 'w') as f:
            f.write(t)
        return t

def from_url(url):
    t = from_url_raw(url)
    return lxml.html.fromstring(t)

def process_xpath(d, h, xpath):
    els = h.xpath(xpath)
    prefix = ''
    for n, el in enumerate(els, 1):
        result = el.xpath('./../..//tr')
        if len(els) != 1:
            prefix = f'{n}_'
        for row in result:
            if len(row) != 2:
                continue
            key = prefix + row[0].text_content().strip()
            value = row[1].text_content().strip()
            if key and value:
                d[key] = value
    return len(els)

def get_long_description(h):
    xpath = '//div [@class="mw-parser-output"]/div [@class="wiki-infobox"][2]'
    e = h.xpath(xpath)[0].getnext()
    ret = ''
    while not isinstance(e, lxml.html.HtmlComment):
        ret += e.text_content()
        e = e.getnext()
    return ret


def get_sessions(sessions):

    for session in sessions:
        url = urllib.parse.urljoin('https://events.ccc.de/', session)
        h = from_url(url)
        d = {}
        title = h.xpath('//h1 [@id="firstHeading"]/text()')[0]
        d['Title'] = title.replace('Session:', '', 1).strip()
        d['Wiki URL'] = url
        try:
            d['Long-Description'] = get_long_description(h)
        except IndexError:
            sys.stderr.write(f'Suspicious URL: {url}\n')
            continue
        process_xpath(d, h, '//th [contains(., "Description")]')
        num_starts = process_xpath(d, h, '//th [contains(., "Starts at")]')
        d['Number of events'] = num_starts
        yield d

def get_sessions_at(sessions, now):
    for d in get_sessions(sessions):
        is_now = False
        num_starts = d['Number of events']
        for i in range(1, num_starts + 1):
            prefix = f'{i}_' if num_starts != 1 else ''
            try:
                start = dateutil.parser.parse(d[prefix + 'Starts at'])
                end = dateutil.parser.parse(d[prefix + 'Ends at'])
                is_now = is_now or (start < now and end > now)
            except ValueError:
                continue
        if is_now and d.get('Language') != 'de - German de - German':
            yield d

def describe_session(n, session):
    desc = session.get("Description") if session.get("Description") != session["Title"] else ''
    return (f'''
        {n}.
        <a href="{session["Wiki URL"]}">
            <strong>{session["Title"]}</strong></a>{(": " + desc) if desc else ""}<br />
    ''')

app = flask.Flask(__name__)
@app.route('/')
def main():
    #from_url = lambda url: lxml.html.fromstring(requests.get(url).text)
    h = from_url('https://events.ccc.de/congress/2019/wiki/index.php/Static:Timetable')
    sessions = {x.split('#')[0] for x in h.xpath('//a [contains(@href, "/congress/2019/wiki/index.php/Session:")]/@href')}

    sessions_now = list(get_sessions_at(sessions, datetime.datetime.now()))
    sessions_now_set = set(tuple(x.items()) for x in sessions_now)

    #print('*** Sessions hour ago ***')
    #now = datetime.datetime.now() - datetime.timedelta(hours=1)
    #to_display = [x for x in get_sessions_at(sessions, now) if tuple(x.items()) not in sessions_now_set]
    #for n, session in enumerate(to_display, 1):
    #    print(f'{n}. {session["Description"]}\n')

    ret = '<html><head><meta http-equiv="refresh" content="5; url=/"></head><body>'
    ret += ('<style>.columns { column-count: 3; } * { margin-bottom: 0.5em; }</style>')

    ret += ('<h1>*** Sessions NOW ***</h1><span class="columns">')
    for n, session in enumerate(sessions_now, 1):
        ret += describe_session(n, session)

    ret += ('</span><h1>*** Sessions in an hour ***</h1><span class="columns">')
    now = datetime.datetime.now() + datetime.timedelta(hours=1)
    to_display = [x for x in get_sessions_at(sessions, now) if tuple(x.items()) not in sessions_now_set]
    for n, session in enumerate(to_display, 1):
        ret += describe_session(n, session)

    return ret

def generate_json():
    h = from_url('https://events.ccc.de/congress/2019/wiki/index.php/Static:Timetable')
    sessions = {x.split('#')[0] for x in h.xpath('//a [contains(@href, "/congress/2019/wiki/index.php/Session:")]/@href')}
    for session in get_sessions(sessions):
        print(json.dumps(session))

if __name__ == '__main__':
    #generate_json()
    app.run()

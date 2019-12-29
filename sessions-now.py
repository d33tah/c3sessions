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


def process_xpath2(h, xpath):
    els = h.xpath(xpath)
    dicts = []
    for n, el in enumerate(els, 1):
        d = {}
        result = el.xpath('./../..//tr')
        for row in result:
            if len(row) != 2:
                continue
            key = row[0].text_content().strip()
            value = row[1].text_content().strip()
            if key and value:
                d[key] = value
        dicts.append(d)
    return tuple(dicts)


def process_xpath(d, h, xpath):
    dicts = process_xpath2(h, xpath)
    for d_add in dicts:
        for key, value in d_add.items():
            d[key] = value


def get_long_description(h):
    xpath = '//div [@class="mw-parser-output"]/div [@class="wiki-infobox"][2]'
    e = h.xpath(xpath)[0].getnext()
    ret = ''
    while not isinstance(e, lxml.html.HtmlComment):
        ret += e.text_content()
        e = e.getnext()
    return ret


def get_sessions():
    h = from_url(
        'https://events.ccc.de/congress/2019/wiki/index.php/Static:Timetable')
    xpath = '//a [contains(@href, "/congress/2019/wiki/index.php/Session:")]/@href'
    session_urls = {x.split('#')[0] for x in h.xpath(xpath)}
    for session_url in session_urls:
        url = urllib.parse.urljoin('https://events.ccc.de/', session_url)
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
        d['Events'] = process_xpath2(h, '//th [contains(., "Starts at")]')
        yield d


def get_sessions_at(now):
    for d in get_sessions():
        is_now = False
        for event in d['Events']:
            try:
                start = dateutil.parser.parse(event['Starts at'])
                end = dateutil.parser.parse(event['Ends at'])
                is_now = is_now or (start < now and end > now)
            except ValueError:
                continue
        if is_now and d.get('Language') != 'de - German de - German':
            yield d


def describe_session(n, session):
    if session.get('Description'):
        desc = ': ' + session['Description']
    else:
        desc = ''
    if len(desc) > 200:
        desc = desc[:desc.find(' ', 200)] + ' (...)'
    return (f'''<li>
        <a href="{session["Wiki URL"]}">
            <strong>{session["Title"]}</strong></a>{desc}</li>
    ''')


app = flask.Flask(__name__)
@app.route('/')
def main():
    #from_url = lambda url: lxml.html.fromstring(requests.get(url).text)
    sessions_now = list(get_sessions_at(datetime.datetime.now()))

    ret = '''<html>
        <head>
            <style>body { column-count: 3; margin-bottom: 0.5em; }</style>
        </head>
    <body>
    <h1>*** Sessions NOW ***</h1><ol>
    '''

    for n, session in enumerate(sessions_now, 1):
        ret += describe_session(n, session)

    ret += '</ol><span style="display: block; break-inside: avoid;">'
    ret += '<h1>*** Sessions in an hour ***</h1><ol>'
    now = datetime.datetime.now() + datetime.timedelta(hours=1)
    to_display = [x for x in get_sessions_at(now) if x not in sessions_now]
    for n, session in enumerate(to_display, 1):
        ret += describe_session(n, session)

    return ret


def generate_json():
    for session in get_sessions():
        print(json.dumps(session))


if __name__ == '__main__':
    # generate_json()
    app.run()

#!/usr/bin/env python

import sys
import datetime
import json
import urllib.parse
import hashlib
import logging

import requests
import flask
import lxml.html
import dateutil.parser

LOGGER = logging.getLogger('c3sessions')


# https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requests_retry_session(
    retries=5,
    backoff_factor=3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = requests.packages.urllib3.util.retry.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def from_url_raw(url):
    fname = f'cache/{hashlib.md5(url.encode()).hexdigest()}'
    try:
        with open(fname) as f:
            return f.read()
    except:
        LOGGER.info('Downloading %r', url)
        session = requests_retry_session()
        t = session.get(url, timeout=1).text
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
        desc = desc[:desc.find(' ', 100)] + ' (...)'
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
            <meta http-equiv="refresh" content="120" />
            <style>
                body {
                    column-count: 3;
                    margin-bottom: 0.5em;
                }
                .footer {
                    position: fixed;
                    left: 0;
                    bottom: 0;
                    width: 100%;
                    text-align: center;
                    border: 1px solid black;
                    background-color: white;
                    color: black;
                }
            </style>
        </head>
    <body>
    <h1>Sessions NOW</h1><ol>
    '''

    for n, session in enumerate(sessions_now, 1):
        ret += describe_session(n, session)

    ret += '</ol>'
    #ret += '<span style="display: block; break-inside: avoid;">'
    ret += '<h1>New sessions in 60min</h1><ol>'
    now = datetime.datetime.now() + datetime.timedelta(minutes=60)
    to_display = [x for x in get_sessions_at(now) if x not in sessions_now]
    for n, session in enumerate(to_display, 1):
        ret += describe_session(n, session)

    ret += '''</ol></span>
    <div class="footer">By d33tah. Source code available
    <a href="https://github.com/d33tah/c3sessions">here</a>.</div>
    </body></html>'''

    return ret


def generate_json():
    for session in get_sessions():
        print(json.dumps(session))


if __name__ == '__main__':
    LOGGING_FORMAT = (
        '[%(levelname)s][%(asctime)s][%(pathname)s:%(lineno)d]: %(message)s'
    )
    logging.basicConfig(format=LOGGING_FORMAT, level='INFO')
    list(get_sessions())  # prepare cache
    # generate_json()
    app.run(host='0.0.0.0')

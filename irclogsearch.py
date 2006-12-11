#!/usr/bin/env python
"""
Search IRC logs (a CGI script).

Expects to find *.log in the directory specified by the IRCLOG_LOCATION
environment variable.  Expects the filenames to contain a ISO 8601 date
(YYYY-MM-DD).
"""

# Copyright (c) 2006, Marius Gedminas 
#
# Released under the terms of the GNU GPL
# http://www.gnu.org/copyleft/gpl.html

import cgi
import sys
import os
import re
import glob
import datetime

import cgitb; cgitb.enable()

from irclog2html import LogParser, XHTMLTableStyle, NickColourizer

logfile_path = os.getenv('IRCLOG_LOCATION')

VERSION = "0.1"
RELEASE = "2006-12-11"

DATE_REGEXP = re.compile('^.*(\d\d\d\d)-(\d\d)-(\d\d)')

HEADER = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=%(charset)s" />
  <title>%(title)s</title>
  <link rel="stylesheet" href="irclog.css" />
  <meta name="generator" content="search.py %(VERSION)s by Marius Gedminas" />
  <meta name="version" content="%(VERSION)s - %(RELEASE)s" />
</head>
<body>""" % {'VERSION': VERSION, 'RELEASE': RELEASE,
             'title': cgi.escape("Search IRC logs"), 'charset': 'UTF-8'}

FOOTER = """
<div class="generatedby">
<p>Generated by search.py %(VERSION)s by <a href="mailto:marius@pov.lt">Marius Gedminas</a>
 - find it at <a href="http://mg.pov.lt/irclog2html/">mg.pov.lt</a>!</p>
</div>
</body>
</html>""" % {'VERSION': VERSION, 'RELEASE': RELEASE}


class Error(Exception):
    """Application error."""


class SearchStats(object):
    """Search statistics."""

    files = 0
    lines = 0
    matches = 0


class SearchResult(object):
    """Search result -- a single utterance."""

    def __init__(self, filename, link, date, time, event, info):
        self.filename = filename
        self.link = link
        self.date = date
        self.time = time
        self.event = event
        self.info = info


class SearchResultFormatter(object):
    """Formatter of search results."""

    def __init__(self):
        self.style = XHTMLTableStyle(sys.stdout)
        self.nick_colour = NickColourizer()

    def print_prefix(self):
        print self.style.prefix

    def print_html(self, result):
        link = cgi.escape(result.link, True)
        if result.event == LogParser.COMMENT:
            nick, text = result.info
            htmlcolour = self.nick_colour[nick]
            self.style.nicktext(result.time, nick, text, htmlcolour, link)
        else:
            if result.event == LogParser.NICKCHANGE:
                text, oldnick, newnick = result.info
                self.nick_colour.change(oldnick, newnick)
            else:
                text = result.info
            self.style.servermsg(result.time, result.event, text, link)

    def print_suffix(self):
        print self.style.suffix


def date_from_filename(filename):
    basename = os.path.basename(filename)
    m = DATE_REGEXP.match(basename)
    if not m:
        raise Error("File name does not contain a YYYY-MM-DD date: %s"
                    % filename)
    return datetime.date(*map(int, m.groups()))


def link_from_filename(filename):
    basename = os.path.basename(filename)
    return basename + '.html'


def search_irc_logs(query, stats=None):
    if not stats:
        stats = SearchStats() # will be discarded, but, oh, well
    query = query.lower()
    files = glob.glob(os.path.join(logfile_path, '*.log'))
    files.sort() # ISO-8601 dates sort the right way
    for filename in files:
        date = date_from_filename(filename)
        link = link_from_filename(filename)
        stats.files += 1
        for time, event, info in LogParser(file(filename)):
            if event == LogParser.COMMENT:
                nick, text = info
                text = nick + ' ' + text
            elif event == LogParser.NICKCHANGE:
                text, oldnick, newnick = info
            else:
                text = str(info)
            stats.lines += 1
            if query in text.lower():
                stats.matches += 1
                yield SearchResult(filename, link, date, time, event, info)


def print_search_form():
    print "Content-Type: text/html; charset=UTF-8"
    print
    print HEADER
    print "<h1>Search IRC logs</h1>"
    print '<form action="" method="post">'
    print '<input type="text" name="q" />'
    print '<input type="submit" />'
    print '</form>'
    print FOOTER


def print_search_results(query):
    print "Content-Type: text/html; charset=UTF-8"
    print
    print HEADER
    print "<h1>IRC log search results for %s</h1>" % cgi.escape(query)
    print '<form action="" method="post">'
    print '<input type="text" name="q" value="%s" />' % cgi.escape(query)
    print '<input type="submit" />'
    print '</form>'
    date = None
    prev_result = None
    formatter = SearchResultFormatter()
    stats = SearchStats()
    for result in search_irc_logs(query, stats):
        if date != result.date:
            if prev_result:
                formatter.print_suffix()
                prev_result = None
            if date:
                print "  </li>"
            else:
                print "<ul>"
            print '  <li><a href="%s">%s</a>:' % (cgi.escape(result.link, True),
                                        result.date.strftime('%Y-%m-%d (%A)'))
            date = result.date
        if not prev_result:
            formatter.print_prefix()
        formatter.print_html(result)
        prev_result = result
    if prev_result:
        formatter.print_suffix()
    if date:
        print "  </li>"
        print "</ul>"
    print "<p>%d matches in %d log files with %d lines.</p>" % (stats.matches,
                                                                stats.files,
                                                                stats.lines)
    print FOOTER


def main():
    form = cgi.FieldStorage()
    if not form.has_key("q"):
        print_search_form()
        return
    search_text = form["q"].value
    print_search_results(search_text)


if __name__ == '__main__':
    main()

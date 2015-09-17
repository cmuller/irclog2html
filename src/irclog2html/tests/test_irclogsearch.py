import cgi
import datetime
import doctest
import gzip
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import closing

import mock
from zope.testing import renormalizing

from irclog2html.irclogsearch import (
    SearchResult, SearchResultFormatter, LogParser, search_irc_logs,
    print_search_form, print_search_results, search_page, get_path, wsgi, main)


try:
    unicode
except NameError:
    # Python 3.x
    unicode = str


here = os.path.dirname(__file__)


class BytesIOWrapper(object):
    charset = 'UTF-8'
    closed = False

    def __init__(self, stream):
        self.stream = stream

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def flush(self):
        self.stream.flush()

    def write(self, bytestr):
        self.stream.write(bytestr.decode(self.charset))
        self.stream.flush()


def myrepr(o):
    """Repr that drops u prefixes on unicode strings."""
    if isinstance(o, tuple):
        if len(o) == 1:
            return '(%s, )' % ', '.join(map(myrepr, o))
        else:
            return '(%s)' % ', '.join(map(myrepr, o))
    elif isinstance(o, unicode):
        return repr(o).lstrip('u')
    else:
        return repr(o)


def doctest_SearchResultFormatter():
    """Test for SearchResultFormatter

        >>> sys.stdout.buffer = BytesIOWrapper(sys.stdout)
        >>> srf = SearchResultFormatter(sys.stdout)
        >>> srf.print_prefix()
        <table class="irclog">

        >>> srf.print_html(SearchResult(
        ...     filename='/path/to/log', link='log.html',
        ...     date=datetime.date(2013, 3, 17), time='12:34',
        ...     event=LogParser.COMMENT, info=('mgedmin', 'hi')))
        <tr id="t12:34"><th class="nick" style="background: #407a40">mgedmin</th><td class="text" style="color: #407a40">hi</td><td class="time"><a href="log.html#t12:34" class="time">12:34</a></td></tr>

        >>> srf.print_html(SearchResult(
        ...     filename='/path/to/log', link='log.html',
        ...     date=datetime.date(2013, 3, 17), time='12:34',
        ...     event=LogParser.NICKCHANGE, info=('mgedmin is now known as mg_away', 'mgedmin', 'mg_away')))
        <tr id="t12:34"><td class="nickchange" colspan="2">mgedmin is now known as mg_away</td><td><a href="log.html#t12:34" class="time">12:34</a></td></tr>

        >>> srf.print_html(SearchResult(
        ...     filename='/path/to/log', link='log.html',
        ...     date=datetime.date(2013, 3, 17), time='12:34',
        ...     event=LogParser.ACTION, info='* mgedmin jumps up and down'))
        <tr id="t12:34"><td class="action" colspan="2">* mgedmin jumps up and down</td><td><a href="log.html#t12:34" class="time">12:34</a></td></tr>

        >>> srf.print_suffix()
        </table>

    """


def gzip_copy(src, dst):
    with open(src, 'rb') as fi:
        with closing(gzip.open(dst, 'wb')) as fo:
            shutil.copyfileobj(fi, fo)


def set_up_sample():
    tmpdir = tempfile.mkdtemp(prefix='irclog2html-test-')
    gzip_copy(os.path.join(here, 'sample.log'),
              os.path.join(tmpdir, 'sample-2013-03-17.log.gz'))
    shutil.copy(os.path.join(here, 'sample.log'),
                os.path.join(tmpdir, 'sample-2013-03-18.log'))
    with open(os.path.join(tmpdir, "index.html"), "w") as f:
        f.write("This is the index")
    return tmpdir


def clean_up_sample(tmpdir):
    shutil.rmtree(tmpdir)


def doctest_search_irc_logs():
    """Test for search_irc_logs

        >>> tmpdir = set_up_sample()
        >>> for r in search_irc_logs('seen', where=tmpdir):
        ...     print('%s %s %s %s %s' % (r.link, r.date, r.time, r.event, myrepr(r.info)))
        sample-2013-03-18.log.html 2013-03-18 2005-01-08T23:47:17 COMMENT ('mgedmin', 'seen mgedmin')
        sample-2013-03-18.log.html 2013-03-18 2005-01-08T23:47:19 COMMENT ('mgedmin', '!seen mgedmin')
        sample-2013-03-18.log.html 2013-03-18 2005-01-08T23:47:19 COMMENT ('povbot', 'mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: <mgedmin> seen mgedmin')
        sample-2013-03-17.log.html 2013-03-17 2005-01-08T23:47:17 COMMENT ('mgedmin', 'seen mgedmin')
        sample-2013-03-17.log.html 2013-03-17 2005-01-08T23:47:19 COMMENT ('mgedmin', '!seen mgedmin')
        sample-2013-03-17.log.html 2013-03-17 2005-01-08T23:47:19 COMMENT ('povbot', 'mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: <mgedmin> seen mgedmin')

        >>> clean_up_sample(tmpdir)

    """


def doctest_print_search_form():
    """Test for print_search_form

        >>> print_search_form()
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html>
        <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title>Search IRC logs</title>
          <link rel="stylesheet" href="irclog.css" />
          <meta name="generator" content="irclogsearch.py ... by Marius Gedminas" />
          <meta name="version" content="..." />
        </head>
        <body>
        <h1>Search IRC logs</h1>
        <form action="" method="get">
        <input type="text" name="q" />
        <input type="submit" />
        </form>
        <BLANKLINE>
        <div class="generatedby">
        <p>Generated by irclogsearch.py ... by <a href="mailto:marius@pov.lt">Marius Gedminas</a>
         - find it at <a href="http://mg.pov.lt/irclog2html/">mg.pov.lt</a>!</p>
        </div>
        </body>
        </html>

    """


def doctest_print_search_results():
    r"""Test for print_search_results

        >>> tmpdir = set_up_sample()
        >>> sys.stdout.buffer = BytesIOWrapper(sys.stdout)
        >>> fmt = print_search_results('povbot', where=tmpdir)
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html>
        <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title>Search IRC logs</title>
          <link rel="stylesheet" href="irclog.css" />
          <meta name="generator" content="irclogsearch.py ... by Marius Gedminas" />
          <meta name="version" content="..." />
        </head>
        <body>
        <h1>IRC log search results for povbot</h1>
        <form action="" method="get">
        <input type="text" name="q" value="povbot" />
        <input type="submit" />
        </form>
        <ul class="searchresults">
          <li><a href="sample-2013-03-18.log.html">2013-03-18 (Monday)</a>:
        <table class="irclog">
        <tr id="t2005-01-08T23:33:54"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-18.log.html#t2005-01-08T23:33:54" class="time">23:33</a></td></tr>
        <tr id="t2005-01-08T23:46:35"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-18.log.html#t2005-01-08T23:46:35" class="time">23:46</a></td></tr>
        <tr id="t2005-01-08T23:47:19"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: &lt;mgedmin&gt; seen mgedmin</td><td class="time"><a href="sample-2013-03-18.log.html#t2005-01-08T23:47:19" class="time">23:47</a></td></tr>
        <tr id="t2005-01-08T23:47:54"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: web1913, jargon, foldoc, vera, and wn responded: vera: BOT Beginning Of Tape; vera: BOT Broadcast Online TV; web1913: Bot \Bot\, n. (Zo[&quot;o]l.) See {Bots}; vera: BOT Build, Operate and Transfer (networke); vera: BOT Back On Topic (telecommunication-slang, Usenet, IRC); wn: bot n : botfly larva; typically develops inside the body of a horse or sheep or human; foldoc: bot &lt;networking, chat, (6 more messages)</td><td class="time"><a href="sample-2013-03-18.log.html#t2005-01-08T23:47:54" class="time">23:47</a></td></tr>
        </table>
          </li>
          <li><a href="sample-2013-03-17.log.html">2013-03-17 (Sunday)</a>:
        <table class="irclog">
        <tr id="t2005-01-08T23:33:54"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-17.log.html#t2005-01-08T23:33:54" class="time">23:33</a></td></tr>
        <tr id="t2005-01-08T23:46:35"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-17.log.html#t2005-01-08T23:46:35" class="time">23:46</a></td></tr>
        <tr id="t2005-01-08T23:47:19"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: &lt;mgedmin&gt; seen mgedmin</td><td class="time"><a href="sample-2013-03-17.log.html#t2005-01-08T23:47:19" class="time">23:47</a></td></tr>
        <tr id="t2005-01-08T23:47:54"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: web1913, jargon, foldoc, vera, and wn responded: vera: BOT Beginning Of Tape; vera: BOT Broadcast Online TV; web1913: Bot \Bot\, n. (Zo[&quot;o]l.) See {Bots}; vera: BOT Build, Operate and Transfer (networke); vera: BOT Back On Topic (telecommunication-slang, Usenet, IRC); wn: bot n : botfly larva; typically develops inside the body of a horse or sheep or human; foldoc: bot &lt;networking, chat, (6 more messages)</td><td class="time"><a href="sample-2013-03-17.log.html#t2005-01-08T23:47:54" class="time">23:47</a></td></tr>
        </table>
          </li>
        </ul>
        <p>8 matches in 2 log files with 20 lines (... seconds).</p>
        <BLANKLINE>
        <div class="generatedby">
        <p>Generated by irclogsearch.py ... by <a href="mailto:marius@pov.lt">Marius Gedminas</a>
         - find it at <a href="http://mg.pov.lt/irclog2html/">mg.pov.lt</a>!</p>
        </div>
        </body>
        </html>

        >>> clean_up_sample(tmpdir)

    """


def doctest_search_page():
    """Test search_page
    Let's mock the dependency functions:

        >>> patcher = mock.patch.multiple("irclog2html.irclogsearch",
        ...                               print_search_form=mock.DEFAULT,
        ...                               print_search_results=mock.DEFAULT)

        >>> values = patcher.start()
        >>> values['print_search_results'].return_value = "Formatter"

    When there is a 'q' param in the GET query, the logs are searched:

        >>> form = cgi.FieldStorage(
        ...     environ={'QUERY_STRING': 'q=123', 'HTTP_METHOD': 'GET'})
        >>> search_page("The stream", form, "/logs", "#dev*.logs")
        'Formatter'
        >>> values['print_search_results'].assert_called_once_with(
        ...     '123', logfile_pattern='#dev*.logs',
        ...     stream='The stream', where='/logs')

    When there is no query, the search form is displayed:

        >>> form = cgi.FieldStorage(environ={
        ...     'HTTP_METHOD': 'GET', 'QUERY_STRING': ''})
        >>> search_page("The stream", form, "/logs", "#dev*.logs")
        >>> values['print_search_form'].assert_called_once_with('The stream')

    Clean up:

        >>> patcher.stop()

    """


def doctest_get_path():
    """Test for get_path.

    This function decides whether to search or to display a file based
    on URL path:

        >>> get_path(dict(PATH_INFO='/search'))
        'search'

        >>> get_path(dict(PATH_INFO='/#channel-2015-05-05.log.html'))
        '#channel-2015-05-05.log.html'

    When there is no file name, we show the index:

        >>> get_path(dict(PATH_INFO='/'))
        'index.html'

    Any slashes other than the leading one result in None:

        >>> get_path(dict(PATH_INFO='/../../etc/passwd'))

    """


def doctest_wsgi():
    r"""Test for the wsgi entry point

        >>> tmpdir = set_up_sample()
        >>> start_response = mock.MagicMock()

        >>> environ = {
        ...     'IRCLOG_LOCATION': tmpdir,
        ...     'PATH_INFO': "/",
        ...     'wsgi.input': None,
        ... }

    When accessing the root, we get the index:

        >>> wsgi(environ, start_response)
        [b'This is the index']
        >>> start_response.assert_called_once_with(
        ...     '200 Ok', [('Content-Type', 'text/html; charset=UTF-8')])

    Accessing the search page:

        >>> environ['PATH_INFO'] = '/search'
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'<!DOCTYPE html PUBLIC...<title>Search IRC logs</title>...
        >>> start_response.assert_called_once_with(
        ...    '200 Ok', [('Content-Type', 'text/html; charset=UTF-8')])

    Searching the logs:

        >>> environ['PATH_INFO'] = '/search'
        >>> environ['QUERY_STRING'] = 'q=bot'
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'...<p>10 matches in 2 log files with 20 lines (... seconds).</p>...
        >>> start_response.assert_called_once_with(
        ...    '200 Ok', [('Content-Type', 'text/html; charset=UTF-8')])

    Retrieving log files:

        >>> environ['PATH_INFO'] = '/sample-2013-03-18.log'
        >>> del environ['QUERY_STRING']
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'2005-01-08T23:33:54 *** povbot has joined #pov...
        >>> start_response.assert_called_once_with(
        ...    '200 Ok', [('Content-Type', 'text/plain')])

    Accessing paths with slashes:

        >>> environ['PATH_INFO'] = '/./index.html'
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'Not found']
        >>> start_response.assert_called_once_with(
        ...    '404 Not Found', [('Content-Type', 'text/html; charset=UTF-8')])

    What if some poor soul runs Windows?

        >>> environ['PATH_INFO'] = '/.\\index.html'
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'Not found']
        >>> start_response.assert_called_once_with(
        ...    '404 Not Found', [('Content-Type', 'text/html; charset=UTF-8')])

    Accessing non-existing files:

        >>> environ['PATH_INFO'] = '/nonexistent'
        >>> start_response = mock.MagicMock()
        >>> wsgi(environ, start_response)
        [b'Not found']
        >>> start_response.assert_called_once_with(
        ...    '404 Not Found', [('Content-Type', 'text/html; charset=UTF-8')])

    Clean up:

        >>> clean_up_sample(tmpdir)
    """


def doctest_main_prints_form():
    """Test for main

        >>> os.environ.pop('QUERY_STRING', None)
        >>> sys.stdout = io.TextIOWrapper(BytesIOWrapper(sys.stdout)) # it's gonna be rewrapped
        >>> main()
        Content-Type: text/html; charset=UTF-8
        <BLANKLINE>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html>
        <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title>Search IRC logs</title>
          <link rel="stylesheet" href="irclog.css" />
          <meta name="generator" content="irclogsearch.py ... by Marius Gedminas" />
          <meta name="version" content="..." />
        </head>
        <body>
        <h1>Search IRC logs</h1>
        <form action="" method="get">
        <input type="text" name="q" />
        <input type="submit" />
        </form>
        <BLANKLINE>
        <div class="generatedby">
        <p>Generated by irclogsearch.py ... by <a href="mailto:marius@pov.lt">Marius Gedminas</a>
         - find it at <a href="http://mg.pov.lt/irclog2html/">mg.pov.lt</a>!</p>
        </div>
        </body>
        </html>

    """


def doctest_main_searches():
    """Test for main

        >>> tmpdir = set_up_sample()
        >>> sys.stdout = io.TextIOWrapper(BytesIOWrapper(sys.stdout)) # it's gonna be rewrapped
        >>> os.environ['QUERY_STRING'] = 'q=povbot'
        >>> os.environ['IRCLOG_LOCATION'] = tmpdir
        >>> os.environ['IRCLOG_GLOB'] = '*.log'
        >>> main()
        Content-Type: text/html; charset=UTF-8
        <BLANKLINE>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html>
        <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <title>Search IRC logs</title>
          <link rel="stylesheet" href="irclog.css" />
          <meta name="generator" content="irclogsearch.py ... by Marius Gedminas" />
          <meta name="version" content="..." />
        </head>
        <body>
        <h1>IRC log search results for povbot</h1>
        <form action="" method="get">
        <input type="text" name="q" value="povbot" />
        <input type="submit" />
        </form>
        <ul class="searchresults">
          <li><a href="sample-2013-03-18.log.html">2013-03-18 (Monday)</a>:
        <table class="irclog">
        <tr id="t2005-01-08T23:33:54"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-18.log.html#t2005-01-08T23:33:54" class="time">23:33</a></td></tr>
        <tr id="t2005-01-08T23:46:35"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-18.log.html#t2005-01-08T23:46:35" class="time">23:46</a></td></tr>
        <tr id="t2005-01-08T23:47:19"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: &lt;mgedmin&gt; seen mgedmin</td><td class="time"><a href="sample-2013-03-18.log.html#t2005-01-08T23:47:19" class="time">23:47</a></td></tr>
        <tr id="t2005-01-08T23:47:54"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: web1913, jargon, foldoc, vera, and wn responded: vera: BOT Beginning Of Tape; vera: BOT Broadcast Online TV; web1913: Bot \Bot\, n. (Zo[&quot;o]l.) See {Bots}; vera: BOT Build, Operate and Transfer (networke); vera: BOT Back On Topic (telecommunication-slang, Usenet, IRC); wn: bot n : botfly larva; typically develops inside the body of a horse or sheep or human; foldoc: bot &lt;networking, chat, (6 more messages)</td><td class="time"><a href="sample-2013-03-18.log.html#t2005-01-08T23:47:54" class="time">23:47</a></td></tr>
        </table>
          </li>
          <li><a href="sample-2013-03-17.log.html">2013-03-17 (Sunday)</a>:
        <table class="irclog">
        <tr id="t2005-01-08T23:33:54"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-17.log.html#t2005-01-08T23:33:54" class="time">23:33</a></td></tr>
        <tr id="t2005-01-08T23:46:35"><td class="join" colspan="2">*** povbot has joined #pov</td><td><a href="sample-2013-03-17.log.html#t2005-01-08T23:46:35" class="time">23:46</a></td></tr>
        <tr id="t2005-01-08T23:47:19"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: mgedmin was last seen in #pov 2 seconds ago saying: &lt;mgedmin&gt; seen mgedmin</td><td class="time"><a href="sample-2013-03-17.log.html#t2005-01-08T23:47:19" class="time">23:47</a></td></tr>
        <tr id="t2005-01-08T23:47:54"><th class="nick" style="background: #407a40">povbot</th><td class="text" style="color: #407a40">mgedmin: web1913, jargon, foldoc, vera, and wn responded: vera: BOT Beginning Of Tape; vera: BOT Broadcast Online TV; web1913: Bot \Bot\, n. (Zo[&quot;o]l.) See {Bots}; vera: BOT Build, Operate and Transfer (networke); vera: BOT Back On Topic (telecommunication-slang, Usenet, IRC); wn: bot n : botfly larva; typically develops inside the body of a horse or sheep or human; foldoc: bot &lt;networking, chat, (6 more messages)</td><td class="time"><a href="sample-2013-03-17.log.html#t2005-01-08T23:47:54" class="time">23:47</a></td></tr>
        </table>
          </li>
        </ul>
        <p>8 matches in 2 log files with 20 lines (... seconds).</p>
        <BLANKLINE>
        <div class="generatedby">
        <p>Generated by irclogsearch.py ... by <a href="mailto:marius@pov.lt">Marius Gedminas</a>
         - find it at <a href="http://mg.pov.lt/irclog2html/">mg.pov.lt</a>!</p>
        </div>
        </body>
        </html>
        >>> clean_up_sample(tmpdir)

    """


checker = None
if sys.version_info[0] == 2:
    checker = renormalizing.RENormalizing([
        (re.compile(r"^\['"), r"[b'"),
        (re.compile(r"u('.*?')"), r"\1"),
    ])


def test_suite():
    optionflags = (doctest.ELLIPSIS | doctest.REPORT_NDIFF |
                   doctest.NORMALIZE_WHITESPACE)
    return unittest.TestSuite([
        doctest.DocTestSuite(optionflags=optionflags, checker=checker),
    ])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

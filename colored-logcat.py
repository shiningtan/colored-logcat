#!/usr/bin/python

'''
    Copyright 2009, The Android Open Source Project

    Licensed under the Apache License, Version 2.0 (the "License"); 
    you may not use this file except in compliance with the License. 
    You may obtain a copy of the License at 

        http://www.apache.org/licenses/LICENSE-2.0 

    Unless required by applicable law or agreed to in writing, software 
    distributed under the License is distributed on an "AS IS" BASIS, 
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
    See the License for the specific language governing permissions and 
    limitations under the License.
'''

# script to highlight adb logcat output for console
# written by jeff sharkey, http://jsharkey.org/
# piping detection and popen() added by other android team members


import os, sys, re, StringIO
import fcntl, termios, struct

# unpack the current terminal width/height
data = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, '1234')
HEIGHT, WIDTH = struct.unpack('hh',data)

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

def format(fg=None, bg=None, bright=False, bold=False, dim=False, reset=False):
    # manually derived from http://en.wikipedia.org/wiki/ANSI_escape_code#Codes
    codes = []
    if reset: codes.append("0")
    else:
        if not fg is None: codes.append("3%d" % (fg))
        if not bg is None:
            if not bright: codes.append("4%d" % (bg))
            else: codes.append("10%d" % (bg))
        if bold: codes.append("1")
        elif dim: codes.append("2")
        else: codes.append("22")
    return "\033[%sm" % (";".join(codes))
    

def indent_wrap(message, indent=0, width=80):
    wrap_area = width - indent
    messagebuf = StringIO.StringIO()
    current = 0
    while current < len(message):
        next = min(current + wrap_area, len(message))
        messagebuf.write(message[current:next])
        if next < len(message):
            messagebuf.write("\n%s" % (" " * indent))
        current = next
    return messagebuf.getvalue()


LAST_USED = [GREEN,YELLOW,BLUE,MAGENTA,CYAN,BLACK]
KNOWN_TAGS = {
    "dalvikvm": BLUE,
    "Process": BLUE,
    "ActivityManager": CYAN,
    "ActivityThread": CYAN,
}

def allocate_color(tag):
    # this will allocate a unique format for the given tag
    # since we dont have very many colors, we always keep track of the LRU
    if not tag in KNOWN_TAGS:
        KNOWN_TAGS[tag] = LAST_USED[0]
    color = KNOWN_TAGS[tag]
    LAST_USED.remove(color)
    LAST_USED.append(color)
    return color

def allocate_color_pid(pid):
    # this will allocate a unique format for the given tag
    # since we dont have very many colors, we always keep track of the LRU
    color = LAST_USED[int(pid) % 6]
    return color

RULES = {
    #re.compile(r"([\w\.@]+)=([\w\.@]+)"): r"%s\1%s=%s\2%s" % (format(fg=BLUE), format(fg=GREEN), format(fg=BLUE), format(reset=True)),
}

TAGTYPE_WIDTH = 3
TAG_WIDTH = 25
PROCESS_WIDTH = 21 #8 # 8 or -1
HEADER_SIZE = TAGTYPE_WIDTH + 1 + TAG_WIDTH + 1 + PROCESS_WIDTH + 1

TAGTYPES = {
    "V": "%s%s%s " % (format(fg=WHITE, bg=BLACK), "V".center(TAGTYPE_WIDTH), format(reset=True)),
    "D": "%s%s%s " % (format(fg=BLACK, bg=BLUE), "D".center(TAGTYPE_WIDTH), format(reset=True)),
    "I": "%s%s%s " % (format(fg=BLACK, bg=GREEN), "I".center(TAGTYPE_WIDTH), format(reset=True)),
    "W": "%s%s%s " % (format(fg=BLACK, bg=YELLOW), "W".center(TAGTYPE_WIDTH), format(reset=True)),
    "E": "%s%s%s " % (format(fg=BLACK, bg=RED), "E".center(TAGTYPE_WIDTH), format(reset=True)),
}

#retag = re.compile("^([A-Z])/([^\(]+)\(([^\)]+)\): (.*)$")
#retag = re.compile("^([0-9][0-9]-[0-9][0-9]) ([0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9]) ([A-Z])/([^\(]+)\(([^\)]+)\): (.*)$")

#11-06 15:49:43.757   640   640 D dalvikvm: GC freed 9163 objects / 524384 bytes in 158ms
retag = re.compile("^([0-9][0-9]-[0-9][0-9]) ([0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9])\s+(\d+)\s+(\d+) ([A-Z]) ([^:]*)[: +](.*)$")

# to pick up -d or -e
#adb_args = ' '.join(sys.argv[1:])

# if someone is piping in to us, use stdin as input.  if not, invoke adb logcat
if os.isatty(sys.stdin.fileno()):
    input = os.popen("adb logcat -v threadtime")
else:
    input = sys.stdin
if len(sys.argv) == 2:
    highlight = format(fg=WHITE, bg=RED, bold=True) + sys.argv[1] + format(reset=True)
    highlight_err = highlight + format(fg=RED, bold=True)
    print "Highlight Keyword: " + highlight

pid_btld = "0"
while True:
    try:
        line = input.readline()
    except KeyboardInterrupt:
        break

    match = retag.match(line)
    if not match is None:
        date, time, pid, tid, tagtype, tag, message = match.groups()
        linebuf = StringIO.StringIO()

        # center process info
        #owner = owner.strip()
        tag = tag.strip()
        if tag == "BTLD":
            pid_btld = pid
        if pid == pid_btld:
            color = RED
        else:
            color = allocate_color_pid(pid)
		
        if len(pid) == 2: pid = " " + pid
        if len(pid) == 1: pid = "  " + pid
        if len(tid) == 2: tid += " "
        if len(tid) == 1: tid += "  "
		
        time = time + ' ' + pid + '/' + tid
        linebuf.write("%s%s%s " % (format(fg=color, dim=False), time, format(reset=True)))

        # right-align tag title and allocate color if needed
         
        tag = tag[-TAG_WIDTH:].rjust(TAG_WIDTH)
        linebuf.write("%s%s %s" % (format(fg=color, dim=False), tag, format(reset=True)))

        # write out tagtype colored edge
        if not tagtype in TAGTYPES: break
        linebuf.write(TAGTYPES[tagtype])

        # insert line wrapping as needed
        if tagtype == "E":
            if len(sys.argv) == 2:
                message = message.replace(sys.argv[1], highlight_err)
            linebuf.write("%s%s%s" % (format(fg=RED, bold=True), message, format(reset=True)))
        #elif tagtype == "W":
        #    linebuf.write("%s%s%s" % (format(fg=YELLOW, bold=True, dim=True), message, format(reset=True)))
        else:
            if len(sys.argv) == 2:
                message = message.replace(sys.argv[1], highlight)
            linebuf.write(message)

        #message = indent_wrap(message, HEADER_SIZE, WIDTH)

        # format tag message using rules
        #for matcher in RULES:
        #    replace = RULES[matcher]
        #    message = matcher.sub(replace, message)
        
        line = linebuf.getvalue()

    print line
    if len(line) == 0: break










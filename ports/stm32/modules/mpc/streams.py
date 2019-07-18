# -*- coding: utf-8 -*-
"""
    pyte.streams
    ~~~~~~~~~~~~

    This module provides three stream implementations with different
    features; for starters, here's a quick example of how streams are
    typically used:


    >>> screen = Screen(80, 24)
    >>> stream = Stream(screen)
    >>> stream.feed("\x1b[5B")  # Move the cursor down 5 rows.
    >>> screen.cursor.y
    5

    :copyright: (c) 2011-2012 by Selectel.
    :copyright: (c) 2012-2017 by pyte authors and contributors,
                    see AUTHORS for details.
    :license: LGPL, see LICENSE for more details.
"""

import ure

#: *Space*: Not suprisingly -- ``" "``.
SP = " "

#: *Null*: Does nothing.
NUL = "\x00"

#: *Bell*: Beeps.
BEL = "\x07"

#: *Backspace*: Backspace one column, but not past the begining of the
#: line.
BS = "\x08"

#: *Horizontal tab*: Move cursor to the next tab stop, or to the end
#: of the line if there is no earlier tab stop.
HT = "\x09"

#: *Linefeed*: Give a line feed, and, if :data:`pyte.modes.LNM` (new
#: line mode) is set also a carriage return.
LF = "\n"
#: *Vertical tab*: Same as :data:`LF`.
VT = "\x0b"
#: *Form feed*: Same as :data:`LF`.
FF = "\x0c"

#: *Carriage return*: Move cursor to left margin on current line.
CR = "\r"

#: *Shift out*: Activate G1 character set.
SO = "\x0e"

#: *Shift in*: Activate G0 character set.
SI = "\x0f"

#: *Cancel*: Interrupt escape sequence. If received during an escape or
#: control sequence, cancels the sequence and displays substitution
#: character.
CAN = "\x18"
#: *Substitute*: Same as :data:`CAN`.
SUB = "\x1a"

#: *Escape*: Starts an escape sequence.
ESC = "\x1b"

#: *Delete*: Is ignored.
DEL = "\x7f"

#: *Control sequence introducer*.
CSI_C0 = ESC + "["
CSI_C1 = "\x9b"
CSI = CSI_C0

#: *String terminator*.
ST_C0 = ESC + "\\"
ST_C1 = "\x9c"
ST = ST_C0

#: *Operating system command*.
OSC_C0 = ESC + "]"
OSC_C1 = "\x9d"
OSC = OSC_C0

#: *Reset*.
RIS = "c"

#: *Index*: Move cursor down one line in same column. If the cursor is
#: at the bottom margin, the screen performs a scroll-up.
IND = "D"

#: *Next line*: Same as :data:`pyte.control.LF`.
NEL = "E"

#: Tabulation set: Set a horizontal tab stop at cursor position.
HTS = "H"

#: *Reverse index*: Move cursor up one line in same column. If the
#: cursor is at the top margin, the screen performs a scroll-down.
RI = "M"

#: Save cursor: Save cursor position, character attribute (graphic
#: rendition), character set, and origin mode selection (see
#: :data:`DECRC`).
DECSC = "7"

#: *Restore cursor*: Restore previously saved cursor position, character
#: attribute (graphic rendition), character set, and origin mode
#: selection. If none were saved, move cursor to home position.
DECRC = "8"

# "Sharp" escape sequences.
# -------------------------

#: *Alignment display*: Fill screen with uppercase E's for testing
#: screen focus and alignment.
DECALN = "8"

# ECMA-48 CSI sequences.
# ---------------------

#: *Insert character*: Insert the indicated # of blank characters.
ICH = "@"

#: *Cursor up*: Move cursor up the indicated # of lines in same column.
#: Cursor stops at top margin.
CUU = "A"

#: *Cursor down*: Move cursor down the indicated # of lines in same
#: column. Cursor stops at bottom margin.
CUD = "B"

#: *Cursor forward*: Move cursor right the indicated # of columns.
#: Cursor stops at right margin.
CUF = "C"

#: *Cursor back*: Move cursor left the indicated # of columns. Cursor
#: stops at left margin.
CUB = "D"

#: *Cursor next line*: Move cursor down the indicated # of lines to
#: column 1.
CNL = "E"

#: *Cursor previous line*: Move cursor up the indicated # of lines to
#: column 1.
CPL = "F"

#: *Cursor horizontal align*: Move cursor to the indicated column in
#: current line.
CHA = "G"

#: *Cursor position*: Move cursor to the indicated line, column (origin
#: at ``1, 1``).
CUP = "H"

#: *Erase data* (default: from cursor to end of line).
ED = "J"

#: *Erase in line* (default: from cursor to end of line).
EL = "K"

#: *Insert line*: Insert the indicated # of blank lines, starting from
#: the current line. Lines displayed below cursor move down. Lines moved
#: past the bottom margin are lost.
IL = "L"

#: *Delete line*: Delete the indicated # of lines, starting from the
#: current line. As lines are deleted, lines displayed below cursor
#: move up. Lines added to bottom of screen have spaces with same
#: character attributes as last line move up.
DL = "M"

#: *Delete character*: Delete the indicated # of characters on the
#: current line. When character is deleted, all characters to the right
#: of cursor move left.
DCH = "P"

#: *Erase character*: Erase the indicated # of characters on the
#: current line.
ECH = "X"

#: *Horizontal position relative*: Same as :data:`CUF`.
HPR = "a"

#: *Device Attributes*.
DA = "c"

#: *Vertical position adjust*: Move cursor to the indicated line,
#: current column.
VPA = "d"

#: *Vertical position relative*: Same as :data:`CUD`.
VPR = "e"

#: *Horizontal / Vertical position*: Same as :data:`CUP`.
HVP = "f"

#: *Tabulation clear*: Clears a horizontal tab stop at cursor position.
TBC = "g"

#: *Set mode*.
SM = "h"

#: *Reset mode*.
RM = "l"

#: *Select graphics rendition*: The terminal can display the following
#: character attributes that change the character display without
#: changing the character (see :mod:`pyte.graphics`).
SGR = "m"

#: *Device status report*.
DSR = "n"

#: *Select top and bottom margins*: Selects margins, defining the
#: scrolling region; parameters are top and bottom line. If called
#: without any arguments, whole screen is used.
DECSTBM = "r"

#: *Horizontal position adjust*: Same as :data:`CHA`.
HPA = "'"


class Stream(object):
    """A stream is a state machine that parses a stream of bytes and
    dispatches events based on what it sees.

    :param pyte.screens.Screen screen: a screen to dispatch events to.
    :param bool strict: check if a given screen implements all required
                        events.

    .. note::

       Stream only accepts text as input, but if for some reason
       you need to feed it with bytes, consider using
       :class:`~pyte.streams.ByteStream` instead.

    .. versionchanged 0.6.0::

       For performance reasons the binding between stream events and
       screen methods was made static. As a result, the stream **will
       not** dispatch events to methods added to screen **after** the
       stream was created.

    .. seealso::

        `man console_codes <http://linux.die.net/man/4/console_codes>`_
            For details on console codes listed bellow in :attr:`basic`,
            :attr:`escape`, :attr:`csi`, :attr:`sharp`.
    """

    #: Control sequences, which don't require any arguments.
    basic = {
        BEL: "bell",
        BS: "backspace",
        HT: "tab",
        LF: "linefeed",
        VT: "linefeed",
        FF: "linefeed",
        CR: "carriage_return",

    }

    #: non-CSI escape sequences.
    escape = {
        RIS: "reset",
        IND: "index",
        NEL: "linefeed",
        RI: "reverse_index",
        HTS: "set_tab_stop",

    }

    #: "sharp" escape sequences -- ``ESC # <N>``.
    sharp = {
        DECALN: "alignment_display",
    }

    #: CSI escape sequences -- ``CSI P1;P2;...;Pn <fn>``.
    csi = {
        ICH: "insert_characters",
        CUU: "cursor_up",
        CUD: "cursor_down",
        CUF: "cursor_forward",
        CUB: "cursor_back",
        CNL: "cursor_down1",
        CPL: "cursor_up1",
        CHA: "cursor_to_column",
        CUP: "cursor_position",
        ED: "erase_in_display",
        EL: "erase_in_line",
        IL: "insert_lines",
        DL: "delete_lines",
        DCH: "delete_characters",
        ECH: "erase_characters",
        HPR: "cursor_forward",

        VPA: "cursor_to_line",
        VPR: "cursor_down",
        HVP: "cursor_position",
        TBC: "clear_tab_stop",
        SM: "set_mode",
        RM: "reset_mode",

        DECSTBM: "set_margins",
        HPA: "cursor_to_column"
    }

    #: A regular expression pattern matching everything what can be
    #: considered plain text.
    _special = set([ESC, CSI_C1, NUL, DEL, OSC_C1])
    _special.update(basic)
    _text_pattern = ure.compile(
        "[^\\\x1b\\\x9d\\\x0b\\\t\\000\\\x08\\\x07\\\n\\\x0c\\\r\\\x9b\\\x7f]+")
    del _special

    def __init__(self, screen=None, strict=True):
        self.listener = None
        self.strict = strict
        self.use_utf8 = True

        if screen is not None:
            self.attach(screen)

    def attach(self, screen):
        """Adds a given screen to the listener queue.

        :param pyte.screens.Screen screen: a screen to attach to.
        """

        self.listener = screen
        self._parser = None
        self._initialize_parser()

    def detach(self, screen):
        """Remove a given screen from the listener queue and fails
        silently if it's not attached.

        :param pyte.screens.Screen screen: a screen to detach.
        """
        if screen is self.listener:
            self.listener = None

    def feed(self, data):
        """Consume some data and advances the state as necessary.

        :param str data: a blob of data to feed from.
        """
        send = self._send_to_parser
        draw = self.listener.draw
        match_text = self._text_pattern.match
        taking_plain_text = self._taking_plain_text

        length = len(data)
        offset = 0
        while offset < length:
            if taking_plain_text:
                old_offset = offset
                match = match_text(data[old_offset:])
                if match:
                    start, offset = match.span()
                    offset += old_offset
                    start += old_offset
                    draw(data[start:offset])
                else:
                    taking_plain_text = False
            else:
                taking_plain_text = send(data[offset:offset + 1])
                offset += 1

        self._taking_plain_text = taking_plain_text

    def _send_to_parser(self, data):
        try:
            return self._parser.send(data)
        except Exception:
            # Reset the parser state to make sure it is usable even
            # after receiving an exception. See PR #101 for details.
            self._initialize_parser()
            raise

    def _initialize_parser(self):
        self._parser = self._parser_fsm()
        self._taking_plain_text = next(self._parser)

    def debug(self, *args, **kwargs):
        pass

    def _parser_fsm(self):
        """An FSM implemented as a coroutine.

        This generator is not the most beautiful, but it is as performant
        as possible. When a process generates a lot of output, then this
        will be the bottleneck, because it processes just one character
        at a time.

        Don't change anything without profiling first.
        """
        basic = self.basic
        listener = self.listener
        draw = listener.draw

        SP_OR_GT = SP + ">"
        NUL_OR_DEL = NUL + DEL
        CAN_OR_SUB = CAN + SUB
        ALLOWED_IN_CSI = "".join([BEL, BS, HT, LF,
                                  VT, FF, CR])
        OSC_TERMINATORS = set([ST_C0, ST_C1, BEL])

        def create_dispatcher(mapping):
            return dict(
                (event, getattr(listener, attr))
                for event, attr in mapping.items())

        basic_dispatch = create_dispatcher(basic)
        sharp_dispatch = create_dispatcher(self.sharp)
        escape_dispatch = create_dispatcher(self.escape)
        csi_dispatch = create_dispatcher(self.csi)

        while True:
            # ``True`` tells ``Screen.feed`` that it is allowed to send
            # chunks of plain text directly to the listener, instead
            # of this generator.
            char = yield True

            if char == ESC:
                # Most non-VT52 commands start with a left-bracket after the
                # escape and then a stream of parameters and a command; with
                # a single notable exception -- :data:`escape.DECOM` sequence,
                # which starts with a sharp.
                #
                # .. versionchanged:: 0.4.10
                #
                #    For compatibility with Linux terminal stream also
                #    recognizes ``ESC % C`` sequences for selecting control
                #    character set. However, in the current version these
                #    are noop.
                char = yield
                if char == "[":
                    char = CSI_C1  # Go to CSI.
                elif char == "]":
                    char = OSC_C1  # Go to OSC.
                else:
                    if char == "#":
                        sharp_dispatch[(yield)]()

                    elif char in "()":
                        code = yield
                        if self.use_utf8:
                            continue

                        # See http://www.cl.cam.ac.uk/~mgk25/unicode.html#term
                        # for the why on the UTF-8 restriction.
                        listener.define_charset(code, mode=char)
                    else:
                        escape_dispatch[char]()
                    continue  # Don't go to CSI.

            if char in basic:
                # Ignore shifts in UTF-8 mode. See
                # http://www.cl.cam.ac.uk/~mgk25/unicode.html#term for
                # the why on UTF-8 restriction.
                if (char == SI or char == SO) and self.use_utf8:
                    continue

                basic_dispatch[char]()
            elif char == CSI_C1:
                # All parameters are unsigned, positive decimal integers, with
                # the most significant digit sent first. Any parameter greater
                # than 9999 is set to 9999. If you do not specify a value, a 0
                # value is assumed.
                #
                # .. seealso::
                #
                #    `VT102 User Guide <http://vt100.net/docs/vt102-ug/>`_
                #        For details on the formatting of escape arguments.
                #
                #    `VT220 Programmer Ref. <http://vt100.net/docs/vt220-rm/>`_
                #        For details on the characters valid for use as
                #        arguments.
                params = []
                current = ""
                private = False
                while True:
                    char = yield
                    if char == "?":
                        private = True
                    elif char in ALLOWED_IN_CSI:
                        basic_dispatch[char]()
                    elif char in SP_OR_GT:
                        pass  # Secondary DA is not supported atm.
                    elif char in CAN_OR_SUB:
                        # If CAN or SUB is received during a sequence, the
                        # current sequence is aborted; terminal displays
                        # the substitute character, followed by characters
                        # in the sequence received after CAN or SUB.
                        draw(char)
                        break
                    elif char.isdigit():
                        current += char
                    elif char == "$":
                        # XTerm-specific ESC]...$[a-z] sequences are not
                        # currently supported.
                        yield
                        break
                    else:
                        params.append(min(int(current or 0), 9999))

                        if char == ";":
                            current = ""
                        else:
                            if private:
                                csi_dispatch[char](*params, private=True)
                            else:
                                csi_dispatch[char](*params)
                            break  # CSI is finished.
            elif char == OSC_C1:
                code = yield
                if code == "R":
                    continue  # Reset palette. Not implemented.
                elif code == "P":
                    continue  # Set palette. Not implemented.

                param = ""
                while True:
                    char = yield
                    if char == ESC:
                        char += yield
                    if char in OSC_TERMINATORS:
                        break
                    else:
                        param += char

                param = param[1:]  # Drop the ;.
                if code in "01":
                    listener.set_icon_name(param)
                if code in "02":
                    listener.set_title(param)
            elif char not in NUL_OR_DEL:
                draw(char)

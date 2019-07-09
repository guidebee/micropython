# -*- coding: utf-8 -*-
"""
    pyte.screens
    ~~~~~~~~~~~~

    This module provides classes for terminal screens, currently
    it contains three screens with different features:

    * :class:`~pyte.screens.Screen` -- base screen implementation,
      which handles all the core escape sequences, recognized by
      :class:`~pyte.streams.Stream`.
    * If you need a screen to keep track of the changed lines
      (which you probably do need) -- use
      :class:`~pyte.screens.DiffScreen`.
    * If you also want a screen to collect history and allow
      pagination -- :class:`pyte.screen.HistoryScreen` is here
      for ya ;)

    .. note:: It would be nice to split those features into mixin
              classes, rather than subclasses, but it's not obvious
              how to do -- feel free to submit a pull request.

    :copyright: (c) 2011-2012 by Selectel.
    :copyright: (c) 2012-2017 by pyte authors and contributors,
                    see AUTHORS for details.
    :license: LGPL, see LICENSE for more details.
"""

from ucollections import namedtuple


LNM = 20

#: *Insert/Replace Mode*: When enabled, new display characters move
#: old display characters to the right. Characters moved past the
#: right margin are lost. Otherwise, new display characters replace
#: old display characters at the cursor position.
IRM = 4


#: *Auto Wrap Mode*: selects where received graphic characters appear
#: when the cursor is at the right margin.
DECAWM = 7 << 5


class DefaultDict:

    @staticmethod
    def __new__(cls, default_factory=None, **kwargs):
        # Some code (e.g. urllib.urlparse) expects that basic defaultdict
        # functionality will be available to subclasses without them
        # calling __init__().
        self = super(DefaultDict, cls).__new__(cls)
        self.d = {}
        return self

    def __init__(self, default_factory=None, **kwargs):
        self.d = kwargs
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return self.d[key]
        except KeyError:
            v = self.__missing__(key)
            self.d[key] = v
            return v

    def __setitem__(self, key, v):
        self.d[key] = v

    def __delitem__(self, key):
        del self.d[key]

    def __contains__(self, key):
        return key in self.d

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        return self.default_factory()

    def clear(self):
        self.d.clear()


#: A container for screen's scroll margins.
Margins = namedtuple("Margins", "top bottom")

Char = namedtuple("Char", "data")

default_char = Char(data=" ")


class Cursor(object):
    """Screen cursor.

    :param int x: 0-based horizontal cursor position.
    :param int y: 0-based vertical cursor position.
    :param pyte.screens.Char attrs: cursor attributes (see
        :meth:`~pyte.screens.Screen.select_graphic_rendition`
        for details).
    """
    __slots__ = ("x", "y", "attrs", "hidden")

    def __init__(self, x, y, attrs=Char(" ")):
        self.x = x
        self.y = y
        self.attrs = attrs
        self.hidden = False


class StaticDefaultDict(dict):

    def __init__(self):
        self.default = default_char

    def __missing__(self, key):
        return self.default


class Screen(object):
    """
    A screen is an in-memory matrix of characters that represents the
    screen display of the terminal. It can be instantiated on its own
    and given explicit commands, or it can be attached to a stream and
    will respond to events.

    .. attribute:: buffer

       A sparse ``lines x columns`` :class:`~pyte.screens.Char` matrix.

    .. attribute:: dirty

       A set of line numbers, which should be re-drawn. The user is responsible
       for clearing this set when changes have been applied.

       >>> screen = Screen(80, 24)
       >>> screen.dirty.clear()
       >>> screen.draw("!")
       >>> list(screen.dirty)
       [0]

       .. versionadded:: 0.7.0

    .. attribute:: cursor

       Reference to the :class:`~pyte.screens.Cursor` object, holding
       cursor position and attributes.


    """

    def __init__(self, columns, lines):
        self.columns = columns
        self.lines = lines
        self.buffer = [[default_char] * columns for _ in range(lines)]
        self.dirty = set()
        self.reset()

    def __repr__(self):
        return ("{0}({1}, {2})".format(self.__class__.__name__,
                                       self.columns, self.lines))

    @property
    def display(self):
        """A :func:`list` of screen lines as unicode strings."""

        def render(line):
            is_wide_char = False
            for x in range(self.columns):
                if is_wide_char:  # Skip stub
                    is_wide_char = False
                    continue
                char = line[x].data
                assert sum(map(len, char[1:])) == 0
                is_wide_char = len(char[0]) == 2
                yield char

        return ["".join(render(self.buffer[y])) for y in range(self.lines)]

    def reset(self):
        """Reset the terminal to its initial state.

        * Scrolling margins are reset to screen boundaries.
        * Cursor is moved to home location -- ``(0, 0)`` and its
          attributes are set to defaults (see :attr:`default_char`).
        * Screen is cleared -- each character is reset to
          :attr:`default_char`.
        * Tabstops are reset to "every eight columns".
        * All lines are marked as :attr:`dirty`.

        .. note::

           Neither VT220 nor VT102 manuals mention that terminal modes
           and tabstops should be reset as well, thanks to
           :manpage:`xterm` -- we now know that.
        """
        self.dirty.update(range(self.lines))
        for r in range(self.lines):
            for c in range(self.columns):
                self.buffer[r][c] = default_char

        self.margins = None

        self.mode = set([DECAWM])

        # From ``man terminfo`` -- "... hardware tabs are initially
        # set every `n` spaces when the terminal is powered up. Since
        # we aim to support VT102 / VT220 and linux -- we use n = 8.
        self.tabstops = set(range(8, self.columns, 8))

        self.cursor = Cursor(0, 0)
        self.cursor_position()

        self.saved_columns = None

    def resize(self, lines=None, columns=None):
        """Resize the screen to the given size.

        If the requested screen size has more lines than the existing
        screen, lines will be added at the bottom. If the requested
        size has less lines than the existing screen lines will be
        clipped at the top of the screen. Similarly, if the existing
        screen has less columns than the requested screen, columns will
        be added at the right, and if it has more -- columns will be
        clipped at the right.

        :param int lines: number of lines in the new screen.
        :param int columns: number of columns in the new screen.

        .. versionchanged:: 0.7.0

           If the requested screen size is identical to the current screen
           size, the method does nothing.
        """
        lines = lines or self.lines
        columns = columns or self.columns

        if lines == self.lines and columns == self.columns:
            return  # No changes.

        self.dirty.update(range(lines))

        if lines < self.lines:
            self.save_cursor()
            self.cursor_position(0, 0)
            self.delete_lines(self.lines - lines)  # Drop from the top.
            self.restore_cursor()

        if columns < self.columns:
            for line in self.buffer.values():
                for x in range(columns, self.columns):
                    line.pop(x, None)

        self.lines, self.columns = lines, columns
        self.set_margins()

    def set_margins(self, top=None, bottom=None):
        """Select top and bottom margins for the scrolling region.

        :param int top: the smallest line number that is scrolled.
        :param int bottom: the biggest line number that is scrolled.
        """
        # XXX 0 corresponds to the CSI with no parameters.
        if (top is None or top == 0) and bottom is None:
            self.margins = None
            return

        margins = self.margins or Margins(0, self.lines - 1)

        # Arguments are 1-based, while :attr:`margins` are zero
        # based -- so we have to decrement them by one. We also
        # make sure that both of them is bounded by [0, lines - 1].
        if top is None:
            top = margins.top
        else:
            top = max(0, min(top - 1, self.lines - 1))
        if bottom is None:
            bottom = margins.bottom
        else:
            bottom = max(0, min(bottom - 1, self.lines - 1))

        # Even though VT102 and VT220 require DECSTBM to ignore
        # regions of width less than 2, some programs (like aptitude
        # for example) rely on it. Practicality beats purity.
        if bottom - top >= 1:
            self.margins = Margins(top, bottom)

            # The cursor moves to the home position when the top and
            # bottom margins of the scrolling region (DECSTBM) changes.
            self.cursor_position()

    def set_mode(self, *modes, **kwargs):
        """Set (enable) a given list of modes.

        :param list modes: modes to set, where each mode is a constant
                           from :mod:`pyte.modes`.
        """
        # Private mode codes are shifted, to be distingiushed from non
        # private ones.
        if kwargs.get("private"):
            modes = [mode << 5 for mode in modes]

        self.mode.update(modes)

    def reset_mode(self, *modes, **kwargs):
        """Reset (disable) a given list of modes.

        :param list modes: modes to reset -- hopefully, each mode is a
                           constant from :mod:`pyte.modes`.
        """
        # Private mode codes are shifted, to be distinguished from non
        # private ones.
        if kwargs.get("private"):
            modes = [mode << 5 for mode in modes]

        self.mode.difference_update(modes)

    def draw(self, data):
        """Display decoded characters at the current cursor position and
        advances the cursor if :data:`~pyte.modes.DECAWM` is set.

        :param str data: text to display.

        .. versionchanged:: 0.5.0

           Character width is taken into account. Specifically, zero-width
           and unprintable characters do not affect screen state. Full-width
           characters are rendered into two consecutive character containers.
        """

        for char in data:
            char_width = len(char)

            # If this was the last column in a line and auto wrap mode is
            # enabled, move the cursor to the beginning of the next line,
            # otherwise replace characters already displayed with newly
            # entered.
            if self.cursor.x == self.columns:
                if DECAWM in self.mode:
                    self.dirty.add(self.cursor.y)
                    self.carriage_return()
                    self.linefeed()
                elif char_width > 0:
                    self.cursor.x -= char_width

            # If Insert mode is set, new characters move old characters to
            # the right, otherwise terminal is in Replace mode and new
            # characters replace old characters at cursor position.
            if IRM in self.mode and char_width > 0:
                self.insert_characters(char_width)

            line = self.buffer[self.cursor.y]
            if char_width == 1:
                line[self.cursor.x] = Char(data=char)

            else:
                break  # Unprintable character or doesn't advance the cursor.

            # .. note:: We can't use :meth:`cursor_forward()`, because that
            #           way, we'll never know when to linefeed.
            if char_width > 0:
                self.cursor.x = min(self.cursor.x + char_width, self.columns)

        self.dirty.add(self.cursor.y)

    def carriage_return(self):
        """Move the cursor to the beginning of the current line."""
        self.cursor.x = 0

    def index(self):
        """Move the cursor down one line in the same column. If the
        cursor is at the last line, create a new line at the bottom.
        """
        top, bottom = self.margins or Margins(0, self.lines - 1)
        if self.cursor.y == bottom:
            # TODO: mark only the lines within margins?
            self.dirty.update(range(self.lines))
            for y in range(top, bottom):
                self.buffer[y] = self.buffer[y + 1]
            self.buffer.pop(bottom)
        else:
            self.cursor_down()

    def reverse_index(self):
        """Move the cursor up one line in the same column. If the cursor
        is at the first line, create a new line at the top.
        """
        top, bottom = self.margins or Margins(0, self.lines - 1)
        if self.cursor.y == top:
            # TODO: mark only the lines within margins?
            self.dirty.update(range(self.lines))
            for y in range(bottom, top, -1):
                self.buffer[y] = self.buffer[y - 1]
            self.buffer.pop(top)
        else:
            self.cursor_up()

    def linefeed(self):
        """Perform an index and, if :data:`~pyte.modes.LNM` is set, a
        carriage return.
        """
        self.index()

        if LNM in self.mode:
            self.carriage_return()

    def tab(self):
        """Move to the next tab space, or the end of the screen if there
        aren't anymore left.
        """
        for stop in sorted(self.tabstops):
            if self.cursor.x < stop:
                column = stop
                break
        else:
            column = self.columns - 1

        self.cursor.x = column

    def backspace(self):
        """Move cursor to the left one or keep it in its position if
        it's at the beginning of the line already.
        """
        self.cursor_back()

    def insert_lines(self, count=None):
        """Insert the indicated # of lines at line with cursor. Lines
        displayed **at** and below the cursor move down. Lines moved
        past the bottom margin are lost.

        :param count: number of lines to insert.
        """
        count = count or 1
        top, bottom = self.margins or Margins(0, self.lines - 1)

        # If cursor is outside scrolling margins it -- do nothin'.
        if top <= self.cursor.y <= bottom:
            self.dirty.update(range(self.cursor.y, self.lines))
            for y in range(bottom, self.cursor.y - 1, -1):
                if y + count <= bottom and y in self.buffer:
                    self.buffer[y + count] = self.buffer[y]
                self.buffer.pop(y, None)

            self.carriage_return()

    def delete_lines(self, count=None):
        """Delete the indicated # of lines, starting at line with
        cursor. As lines are deleted, lines displayed below cursor
        move up. Lines added to bottom of screen have spaces with same
        character attributes as last line moved up.

        :param int count: number of lines to delete.
        """
        count = count or 1
        top, bottom = self.margins or Margins(0, self.lines - 1)

        # If cursor is outside scrolling margins -- do nothin'.
        if top <= self.cursor.y <= bottom:
            self.dirty.update(range(self.cursor.y, self.lines))
            for y in range(self.cursor.y, bottom + 1):
                if y + count <= bottom:
                    if y + count in self.buffer:
                        self.buffer[y] = self.buffer.pop(y + count)
                else:
                    self.buffer.pop(y, None)

            self.carriage_return()

    def insert_characters(self, count=None):
        """Insert the indicated # of blank characters at the cursor
        position. The cursor does not move and remains at the beginning
        of the inserted blank characters. Data on the line is shifted
        forward.

        :param int count: number of characters to insert.
        """
        self.dirty.add(self.cursor.y)

        count = count or 1
        line = self.buffer[self.cursor.y]
        for x in range(self.columns, self.cursor.x - 1, -1):
            if x + count <= self.columns:
                line[x + count] = line[x]
            line.pop(x, None)

    def delete_characters(self, count=None):
        """Delete the indicated # of characters, starting with the
        character at cursor position. When a character is deleted, all
        characters to the right of cursor move left. Character attributes
        move with the characters.

        :param int count: number of characters to delete.
        """
        self.dirty.add(self.cursor.y)
        count = count or 1

        line = self.buffer[self.cursor.y]
        for x in range(self.cursor.x, self.columns):
            if x + count <= self.columns:
                line[x] = line.pop(x + count, default_char)
            else:
                line.pop(x, None)

    def erase_characters(self, count=None):
        """Erase the indicated # of characters, starting with the
        character at cursor position. Character attributes are set
        cursor attributes. The cursor remains in the same position.

        :param int count: number of characters to erase.

        .. note::

           Using cursor attributes for character attributes may seem
           illogical, but if recall that a terminal emulator emulates
           a type writer, it starts to make sense. The only way a type
           writer could erase a character is by typing over it.
        """
        self.dirty.add(self.cursor.y)
        count = count or 1

        line = self.buffer[self.cursor.y]
        for x in range(self.cursor.x,
                       min(self.cursor.x + count, self.columns)):
            line[x] = self.cursor.attrs

    def erase_in_line(self, how=0, private=False):
        """Erase a line in a specific way.

        Character attributes are set to cursor attributes.

        :param int how: defines the way the line should be erased in:

            * ``0`` -- Erases from cursor to end of line, including cursor
              position.
            * ``1`` -- Erases from beginning of line to cursor,
              including cursor position.
            * ``2`` -- Erases complete line.
        :param bool private: when ``True`` only characters marked as
                             eraseable are affected **not implemented**.
        """
        self.dirty.add(self.cursor.y)
        if how == 0:
            interval = range(self.cursor.x, self.columns)
        elif how == 1:
            interval = range(self.cursor.x + 1)
        elif how == 2:
            interval = range(self.columns)

        line = self.buffer[self.cursor.y]
        for x in interval:
            line[x] = self.cursor.attrs

    def erase_in_display(self, how=0, *args, **kwargs):
        """Erases display in a specific way.

        Character attributes are set to cursor attributes.

        :param int how: defines the way the line should be erased in:

            * ``0`` -- Erases from cursor to end of screen, including
              cursor position.
            * ``1`` -- Erases from beginning of screen to cursor,
              including cursor position.
            * ``2`` and ``3`` -- Erases complete display. All lines
              are erased and changed to single-width. Cursor does not
              move.
        :param bool private: when ``True`` only characters marked as
                             eraseable are affected **not implemented**.

        .. versionchanged:: 0.8.1

           The method accepts any number of positional arguments as some
           ``clear`` implementations include a ``;`` after the first
           parameter causing the stream to assume a ``0`` second parameter.
        """
        if how == 0:
            interval = range(self.cursor.y + 1, self.lines)
        elif how == 1:
            interval = range(self.cursor.y)
        elif how == 2 or how == 3:
            interval = range(self.lines)

        self.dirty.update(interval)
        for y in interval:
            line = self.buffer[y]
            for x in line:
                line[x] = self.cursor.attrs

        if how == 0 or how == 1:
            self.erase_in_line(how)

    def set_tab_stop(self):
        """Set a horizontal tab stop at cursor position."""
        self.tabstops.add(self.cursor.x)

    def clear_tab_stop(self, how=0):
        """Clear a horizontal tab stop.

        :param int how: defines a way the tab stop should be cleared:

            * ``0`` or nothing -- Clears a horizontal tab stop at cursor
              position.
            * ``3`` -- Clears all horizontal tab stops.
        """
        if how == 0:
            # Clears a horizontal tab stop at cursor position, if it's
            # present, or silently fails if otherwise.
            self.tabstops.discard(self.cursor.x)
        elif how == 3:
            self.tabstops = set()  # Clears all horizontal tab stops.

    def ensure_hbounds(self):
        """Ensure the cursor is within horizontal screen bounds."""
        self.cursor.x = min(max(0, self.cursor.x), self.columns - 1)

    def ensure_vbounds(self, use_margins=None):
        """Ensure the cursor is within vertical screen bounds.

        :param bool use_margins: when ``True``
                                 cursor is bounded by top and and bottom
                                 margins, instead of ``[0; lines - 1]``.
        """
        if use_margins and self.margins is not None:
            top, bottom = self.margins
        else:
            top, bottom = 0, self.lines - 1

        self.cursor.y = min(max(top, self.cursor.y), bottom)

    def cursor_up(self, count=None):
        """Move cursor up the indicated # of lines in same column.
        Cursor stops at top margin.

        :param int count: number of lines to skip.
        """
        top, _bottom = self.margins or Margins(0, self.lines - 1)
        self.cursor.y = max(self.cursor.y - (count or 1), top)

    def cursor_up1(self, count=None):
        """Move cursor up the indicated # of lines to column 1. Cursor
        stops at bottom margin.

        :param int count: number of lines to skip.
        """
        self.cursor_up(count)
        self.carriage_return()

    def cursor_down(self, count=None):
        """Move cursor down the indicated # of lines in same column.
        Cursor stops at bottom margin.

        :param int count: number of lines to skip.
        """
        _top, bottom = self.margins or Margins(0, self.lines - 1)
        self.cursor.y = min(self.cursor.y + (count or 1), bottom)

    def cursor_down1(self, count=None):
        """Move cursor down the indicated # of lines to column 1.
        Cursor stops at bottom margin.

        :param int count: number of lines to skip.
        """
        self.cursor_down(count)
        self.carriage_return()

    def cursor_back(self, count=None):
        """Move cursor left the indicated # of columns. Cursor stops
        at left margin.

        :param int count: number of columns to skip.
        """
        # Handle the case when we've just drawn in the last column
        # and would wrap the line on the next :meth:`draw()` call.
        if self.cursor.x == self.columns:
            self.cursor.x -= 1

        self.cursor.x -= count or 1
        self.ensure_hbounds()

    def cursor_forward(self, count=None):
        """Move cursor right the indicated # of columns. Cursor stops
        at right margin.

        :param int count: number of columns to skip.
        """
        self.cursor.x += count or 1
        self.ensure_hbounds()

    def cursor_position(self, line=None, column=None):
        """Set the cursor to a specific `line` and `column`.



        :param int line: line number to move the cursor to.
        :param int column: column number to move the cursor to.
        """
        column = (column or 1) - 1
        line = (line or 1) - 1

        if self.margins is not None:
            line += self.margins.top

            # Cursor is not allowed to move out of the scrolling region.
            if not self.margins.top <= line <= self.margins.bottom:
                return

        self.cursor.x = column
        self.cursor.y = line
        self.ensure_hbounds()
        self.ensure_vbounds()

    def cursor_to_column(self, column=None):
        """Move cursor to a specific column in the current line.

        :param int column: column number to move the cursor to.
        """
        self.cursor.x = (column or 1) - 1
        self.ensure_hbounds()

    def cursor_to_line(self, line=None):
        """Move cursor to a specific line in the current column.

        :param int line: line number to move the cursor to.
        """
        self.cursor.y = (line or 1) - 1

        self.ensure_vbounds()

    def bell(self, *args):
        """Bell stub -- the actual implementation should probably be
        provided by the end-user.
        """

    def alignment_display(self):
        """Fills screen with uppercase E's for screen focus and alignment."""
        self.dirty.update(range(self.lines))
        for y in range(self.lines):
            for x in range(self.columns):
                self.buffer[y][x] = Char(data="E")

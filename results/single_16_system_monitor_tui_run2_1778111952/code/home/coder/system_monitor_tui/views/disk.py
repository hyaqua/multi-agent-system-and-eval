"""Disk view: disk usage and I/O."""

import curses
from ..utils import human_readable_bytes, make_bar, format_percent


class DiskView:
    """Renders the disk monitoring view."""

    def draw(self, stdscr, top, height, width, ui):
        """Draw disk view."""
        try:
            y = top

            # Disk usage section
            y = self._draw_disk_usage(stdscr, y, height, width, ui)

            # Disk I/O section
            if y < top + height - 5:
                y += 1
                self._draw_disk_io(stdscr, y, height, width, ui)

        except curses.error:
            pass

    def _draw_disk_usage(self, stdscr, y, total_height, width, ui):
        """Draw filesystem usage."""
        try:
            stdscr.addstr(y, 1, "Filesystem Usage", curses.A_BOLD | curses.color_pair(4))
            y += 1

            header = f" {'Mount':<20} {'Device':<15} {'Total':>10} {'Used':>10} {'Free':>10} {'Use%':>7}"
            stdscr.addstr(y, 0, header[:width], curses.color_pair(6))
            y += 1

            mounts = ui.disk_usage  # Use cached data

            for mnt in mounts:
                if y >= total_height - 10:
                    break

                pct = mnt['percent']
                color = ui.get_color(pct)
                bar_width = 10
                bar = make_bar(pct / 100.0, bar_width)

                mountpoint = mnt['mountpoint'][:19]
                device = mnt['device'][:14]
                total_s = human_readable_bytes(mnt['total'])
                used_s = human_readable_bytes(mnt['used'])
                free_s = human_readable_bytes(mnt['free'])

                line = f" {mountpoint:<20} {device:<15} {total_s:>10} {used_s:>10} {free_s:>10} [{bar}] {pct:4.1f}%"
                line = line[:width]

                bar_start = line.find('[')
                if bar_start >= 0 and bar_start < width:
                    stdscr.addstr(y, 0, line[:bar_start] if bar_start else "")
                    try:
                        bar_end = bar_start + bar_width + 2
                        if bar_end > width:
                            bar_end = width
                        stdscr.addstr(y, bar_start, line[bar_start:bar_end], color)
                        if bar_end < width and bar_end < len(line):
                            stdscr.addstr(y, bar_end, line[bar_end:width])
                    except curses.error:
                        stdscr.addstr(y, 0, line[:width])
                else:
                    stdscr.addstr(y, 0, line[:width])

                y += 1

            return y
        except curses.error:
            return y

    def _draw_disk_io(self, stdscr, y, total_height, width, ui):
        """Draw disk I/O statistics."""
        try:
            stdscr.addstr(y, 1, "Disk I/O (per second)", curses.A_BOLD | curses.color_pair(4))
            y += 1

            header = f" {'Device':<15} {'Read Rate':>14} {'Write Rate':>14}"
            stdscr.addstr(y, 0, header[:width], curses.color_pair(6))
            y += 1

            io_stats = ui.disk_io  # Use cached data

            sorted_devs = sorted(io_stats.items(),
                                 key=lambda x: x[1]['read_rate'] + x[1]['write_rate'],
                                 reverse=True)

            for device, stats in sorted_devs:
                if y >= total_height - 2:
                    break

                read_rate = human_readable_bytes(stats['read_rate']) + "/s"
                write_rate = human_readable_bytes(stats['write_rate']) + "/s"

                line = f" {device:<15} {read_rate:>14} {write_rate:>14}"
                stdscr.addstr(y, 0, line[:width])
                y += 1

            return y
        except curses.error:
            return y

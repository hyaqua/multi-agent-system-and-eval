"""Process listing and management from /proc."""

import os
import pwd
import signal
import time


class ProcessInfo:
    """Holds information about a single process."""

    __slots__ = ('pid', 'user', 'cpu_percent', 'mem_percent', 'state',
                 'cmdline', 'ppid', 'nice', 'rss')

    def __init__(self, pid, user, cpu_percent, mem_percent, state, cmdline,
                 ppid=0, nice_val=0, rss=0):
        self.pid = pid
        self.user = user
        self.cpu_percent = cpu_percent
        self.mem_percent = mem_percent
        self.state = state
        self.cmdline = cmdline
        self.ppid = ppid
        self.nice = nice_val
        self.rss = rss


class ProcessManager:
    """Manages the process list from /proc."""

    def __init__(self):
        self._processes = []
        self._prev_cpu_total = 0
        self._prev_proc_times = {}  # pid -> (utime+stime, timestamp)
        self._total_ram = self._get_total_ram()
        self._sort_key = 'pid'
        self._sort_reverse = False
        self._clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        self._num_cores = self._get_num_cores()

    def _get_total_ram(self):
        """Get total RAM in kB from /proc/meminfo."""
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        parts = line.split()
                        if len(parts) >= 2:
                            return int(parts[1])
        except (IOError, OSError):
            pass
        return 1

    def _get_num_cores(self):
        """Get number of CPU cores from /proc/stat."""
        try:
            with open('/proc/stat', 'r') as f:
                count = 0
                for line in f:
                    if line.startswith('cpu') and line[3].isdigit():
                        count += 1
                return max(1, count)
        except (IOError, OSError):
            return 1

    def _read_file(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except (IOError, OSError, PermissionError):
            return ''

    def _get_uid_for_pid(self, pid):
        """Get UID of a process from /proc/[pid]/status."""
        content = self._read_file(f'/proc/{pid}/status')
        for line in content.split('\n'):
            if line.startswith('Uid:'):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
        return -1

    def _get_username(self, uid):
        try:
            return pwd.getpwuid(uid).pw_name
        except (KeyError, OSError):
            return str(uid)

    def list_processes(self):
        """Scan /proc and return a list of ProcessInfo objects, sorted."""
        pids = []
        try:
            for entry in os.listdir('/proc'):
                if entry.isdigit():
                    pids.append(int(entry))
        except (OSError, PermissionError):
            pass

        # Get total CPU time for this moment
        cpu_total = 0
        try:
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('cpu '):
                        parts = line.split()
                        cpu_total = sum(int(x) for x in parts[1:])
                        break
        except (IOError, OSError):
            pass

        processes = []
        now = time.time()

        for pid in pids:
            try:
                stat = self._read_file(f'/proc/{pid}/stat')
                if not stat:
                    continue
                # Handle cmdline in parentheses which may contain spaces
                # Format: pid (comm) state ppid ...
                close_paren = stat.rfind(')')
                if close_paren == -1:
                    continue

                before_paren = stat[:close_paren]
                open_paren = before_paren.rfind('(')
                if open_paren == -1:
                    continue

                comm = stat[open_paren + 1:close_paren]
                rest = stat[close_paren + 2:].split()

                if len(rest) < 20:
                    continue

                state = rest[0]
                ppid = int(rest[1])
                utime = int(rest[11])
                stime = int(rest[12])
                cutime = int(rest[13])
                cstime = int(rest[14])
                nice_val = int(rest[16])
                rss = int(rest[21])  # pages

                # Get cmdline
                cmdline = self._read_file(f'/proc/{pid}/cmdline').replace('\0', ' ').strip()
                if not cmdline:
                    # fallback to comm from stat
                    cmdline = f'[{comm}]'

                # Get user
                uid = self._get_uid_for_pid(pid)
                user = self._get_username(uid)

                # Calculate CPU%
                total_time = utime + stime + cutime + cstime
                cpu_percent = 0.0
                if pid in self._prev_proc_times and cpu_total != self._prev_cpu_total:
                    prev_total_time, prev_timestamp = self._prev_proc_times[pid]
                    cpu_delta = cpu_total - self._prev_cpu_total
                    proc_delta = total_time - prev_total_time
                    elapsed = now - prev_timestamp
                    if elapsed > 0:
                        # CPU% as percentage of one core (like top does)
                        cpu_percent = (proc_delta / self._clock_ticks) / elapsed * 100.0

                self._prev_proc_times[pid] = (total_time, now)

                # Calculate MEM%
                mem_percent = (rss * os.sysconf('SC_PAGE_SIZE') / 1024) / self._total_ram * 100.0

                processes.append(ProcessInfo(
                    pid=pid,
                    user=user,
                    cpu_percent=cpu_percent,
                    mem_percent=mem_percent,
                    state=state,
                    cmdline=cmdline,
                    ppid=ppid,
                    nice_val=nice_val,
                    rss=rss,
                ))
            except (OSError, PermissionError, FileNotFoundError, ValueError, IndexError):
                continue

        self._prev_cpu_total = cpu_total
        self._processes = self._sort(processes)
        return self._processes

    def _sort(self, processes):
        """Sort the process list by current sort key."""
        if self._sort_key == 'cpu':
            key_fn = lambda p: p.cpu_percent
        elif self._sort_key == 'mem':
            key_fn = lambda p: p.mem_percent
        else:  # pid
            key_fn = lambda p: p.pid

        return sorted(processes, key=key_fn, reverse=self._sort_key != 'pid')

    def sort_by(self, column):
        """Set sort column: 'cpu', 'mem', or 'pid'."""
        self._sort_key = column
        return self._sort(self._processes)

    def search(self, processes, search_str):
        """Filter processes by name containing search_str (case-insensitive)."""
        if not search_str:
            return processes
        s = search_str.lower()
        return [p for p in processes if s in p.cmdline.lower() or s in p.user.lower()]

    def kill(self, pid):
        """Send SIGKILL to a process. Returns (success, message)."""
        try:
            os.kill(pid, signal.SIGKILL)
            return (True, f'Killed PID {pid}')
        except OSError as e:
            return (False, str(e))
        except PermissionError:
            return (False, 'Permission denied')

    def renice(self, pid, nice_val):
        """Renice a process. Returns (success, message)."""
        try:
            nice_val = int(nice_val)
            if nice_val < -20 or nice_val > 19:
                return (False, 'Nice value must be -20 to 19')
            os.setpriority(os.PRIO_PROCESS, pid, nice_val)
            return (True, f'Reniced PID {pid} to {nice_val}')
        except ValueError:
            return (False, 'Invalid nice value')
        except OSError as e:
            return (False, str(e))
        except PermissionError:
            return (False, 'Permission denied (need root)')

    def build_process_tree(self):
        """
        Build a tree structure from process list.
        Returns list of (ProcessInfo, depth, is_last_child) tuples for display.
        """
        processes = self._processes
        if not processes:
            return []

        # Map pid -> ProcessInfo
        pid_map = {p.pid: p for p in processes}
        # Map ppid -> list of children pids
        children = {}
        for p in processes:
            if p.ppid not in children:
                children[p.ppid] = []
            children[p.ppid].append(p.pid)

        # Find roots: processes whose ppid is not in our list, or ppid=0, or ppid=1
        roots = []
        for p in processes:
            if p.ppid not in pid_map or p.ppid == 0:
                roots.append(p.pid)

        # If no roots found, use PID 1 or first process
        if not roots:
            if 1 in pid_map:
                roots = [1]
            elif processes:
                roots = [processes[0].pid]

        result = []

        def traverse(pid, depth, is_last_stack):
            if pid not in pid_map:
                return
            proc = pid_map[pid]
            result.append((proc, depth, list(is_last_stack)))

            kids = children.get(pid, [])
            # Sort kids by pid for consistent display
            kids.sort()
            for i, child_pid in enumerate(kids):
                is_last = (i == len(kids) - 1)
                new_stack = is_last_stack + [is_last]
                traverse(child_pid, depth + 1, new_stack)

        # Sort roots by pid
        roots.sort()
        for i, root_pid in enumerate(roots):
            is_last = (i == len(roots) - 1)
            traverse(root_pid, 0, [is_last])

        return result

# tools/log_parser.py
def count_levels(lines):
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0}
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        level = parts[1]
        if level in counts:
            counts[level] += 1
    return counts

class TopPypiStats:
    _added: list
    _skipped: list
    _omitted: list

    def __init__(self):
        self._added = []
        self._skipped = []
        self._omitted = []

    def add_added(self, package_name: str):
        self._added.append(package_name)

    def add_skipped(self, package_name: str):
        self._skipped.append(package_name)

    def add_omitted(self, package_name: str, package_github: str | None = None, stars_count: int | None = None):
        self._omitted.append(package_name)
        print(f"Omitting partial data for {package_name}. GitHub={package_github} stars={stars_count}")

    def print_stats(self):
        print(f"Added: {self._added}")
        print(f"Skipped: {self._skipped}")
        print(f"Omitted: {self._omitted}")
        print(f"Added={len(self._added)} Skipped={len(self._skipped)} Omitted={len(self._omitted)}")
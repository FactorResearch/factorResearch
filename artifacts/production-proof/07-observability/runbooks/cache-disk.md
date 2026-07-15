# Cache Corruption or Disk Pressure

1. Measure filesystem use and cache decode failures; identify disposable cache paths before deleting anything.
2. Stop cache writers and background downloads when free space is below the safe threshold.
3. Preserve logs and authoritative databases. Never treat a cache as the only copy of user data.
4. Quarantine corrupt entries, reclaim bounded disposable data, and verify permissions/read-only behavior.
5. Warm only critical keys and monitor disk, latency, provider traffic, and error rate.

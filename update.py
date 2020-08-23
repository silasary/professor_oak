from pkmnhelper import populate

populate.hash2phash()

# if subprocess.run(['git', 'diff', '--exit-code', 'phashes.yaml'], check=False).returncode > 0:
#     branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], check=True, capture_output=True).stdout.decode().strip()
#     subprocess.run(['git', 'add', 'phashes.yaml'], check=True)
#     subprocess.run(['git', 'commit', '-m', 'phashes.yaml'], check=True)
#     subprocess.run(['git', 'push', '--force', 'origin', 'head:phash'], check=True)

#     configuration.DEFAULTS.update({'gh_token': ''})
#     token = configuration.get('gh_token')
#     if token:
#         g = Github(token)
#         r = g.get_repo('silasary/professor_oak')
#         r.create_pull(title='Update phashes', body='', base='master', head='phash')

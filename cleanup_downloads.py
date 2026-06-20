import os
import glob

DOWNLOAD_DIR = 'downloads'


def cleanup():
    if not os.path.exists(DOWNLOAD_DIR):
        print(f'Folder {DOWNLOAD_DIR} does not exist.')
        return

    files = glob.glob(os.path.join(DOWNLOAD_DIR, '*'))

    if not files:
        print('Downloads folder is already empty.')
        return

    deleted = 0
    total_size = 0

    for f in files:
        if os.path.isfile(f):
            total_size += os.path.getsize(f)
            os.remove(f)
            deleted += 1
            print(f'Deleted: {os.path.basename(f)}')

    print(f'\nDone: {deleted} files deleted, {total_size / (1024 * 1024):.1f} MB freed')


if __name__ == '__main__':
    cleanup()
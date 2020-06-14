#include <fcntl.h>
#include <linux/msdos_fs.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <stddef.h>

/*
 * This file prints the constants for both VFAT_IOCTL_READDIR_BOTH
 * and VFAT_IOCTL_READDIR_SHORT, as well as the buffer length required
 * for the __fat_dirent structure (multiplied by 2).
 * The output is suitable for direct inclusion into a python module.
 * Also output is a format string suitable for use by struct.unpack().
 *
 * The accompanying Makefile builds this C file into an executable and
 * generates the vfat_ioctl.py Python module from it. This is then
 * imported into the test_short.py program for use in determining
 * the short (8.3 format) filenames.
 */

int main(int argc, char *argv[])
{
    struct __fat_dirent entry;

    printf("VFAT_IOCTL_READDIR_BOTH = %ld\n", VFAT_IOCTL_READDIR_BOTH);
    printf("VFAT_IOCTL_READDIR_SHORT = %ld\n", VFAT_IOCTL_READDIR_SHORT);
    long int buffer_size = sizeof(struct __fat_dirent);
    printf("BUFFER_SIZE = %ld\n", buffer_size * 2);

    long int d_reclen_offset = offsetof(struct __fat_dirent, d_reclen);
    long int d_reclen_size = sizeof(entry.d_reclen);
    char d_reclen_type;
    switch (d_reclen_size) {
        case 1:
            d_reclen_type = 'B';
            break;
        case 2:
            d_reclen_type = 'H';
            break;
        case 4:
            d_reclen_type = 'I';
            break;
    }

    long int d_name_offset = offsetof(struct __fat_dirent, d_name);
    long int d_name_size = sizeof(entry.d_name);

    if (d_reclen_offset + d_reclen_size != d_name_offset) {
        printf("Oops!\n");
    }

    long int end_padding_size = buffer_size - (d_name_offset + d_name_size);

    printf("BUFFER_FORMAT = '=%ldx%c%lds%ldx%ldx%c%lds%ldx'\n",
        d_reclen_offset, d_reclen_type, d_name_size, end_padding_size,
        d_reclen_offset, d_reclen_type, d_name_size, end_padding_size);

    exit(EXIT_SUCCESS);
}

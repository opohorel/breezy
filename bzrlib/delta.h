/*
 * delta.h: headers for delta functionality
 *
 * Adapted from GIT for Bazaar by
 *   John Arbash Meinel <john@arbash-meinel.com> (C) 2009
 *
 * This code is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 */
#ifndef DELTA_H
#define DELTA_H

/* opaque object for delta index */
struct delta_index;

struct source_info {
    const void *buf; /* Pointer to the beginning of source data */
    unsigned long size; /* Total length of source data */
    unsigned long agg_offset; /* Start of source data as part of the
                                 aggregate source */
};

/*
 * create_delta_index: compute index data from given buffer
 *
 * This returns a pointer to a struct delta_index that should be passed to
 * subsequent create_delta() calls, or to free_delta_index().  A NULL pointer
 * is returned on failure.  The given buffer must not be freed nor altered
 * before free_delta_index() is called.  The returned pointer must be freed
 * using free_delta_index().
 */
extern struct delta_index *
create_delta_index(const struct source_info *src,
                   struct delta_index *old);


/*
 * create_delta_index_from_delta: compute index data from given buffer
 *
 * This returns a pointer to a struct delta_index that should be passed to
 * subsequent create_delta() calls, or to free_delta_index().  A NULL pointer
 * is returned on failure.
 * The bytes must be in the form of a delta structure, as generated by
 * create_delta(). The generated index will only index the insert bytes, and
 * not any of the control structures.
 */
extern struct delta_index *
create_delta_index_from_delta(const struct source_info *delta,
                              struct delta_index *old);
/*
 * free_delta_index: free the index created by create_delta_index()
 *
 * Given pointer must be what create_delta_index() returned, or NULL.
 */
extern void free_delta_index(struct delta_index *index);

/*
 * sizeof_delta_index: returns memory usage of delta index
 *
 * Given pointer must be what create_delta_index() returned, or NULL.
 */
extern unsigned long sizeof_delta_index(struct delta_index *index);

/*
 * create_delta: create a delta from given index for the given buffer
 *
 * This function may be called multiple times with different buffers using
 * the same delta_index pointer.  If max_delta_size is non-zero and the
 * resulting delta is to be larger than max_delta_size then NULL is returned.
 * On success, a non-NULL pointer to the buffer with the delta data is
 * returned and *delta_size is updated with its size.  The returned buffer
 * must be freed by the caller.
 */
extern void *
create_delta(const struct delta_index *index,
         const void *buf, unsigned long bufsize,
         unsigned long *delta_size, unsigned long max_delta_size);

/* the smallest possible delta size is 3 bytes
 * Target size, Copy command, Copy length
 */
#define DELTA_SIZE_MIN  3

/*
 * This must be called twice on the delta data buffer, first to get the
 * expected source buffer size, and again to get the target buffer size.
 */
static unsigned long
get_delta_hdr_size(unsigned char **datap, const unsigned char *top)
{
    unsigned char *data = *datap;
    unsigned char cmd;
    unsigned long size = 0;
    int i = 0;
    do {
        cmd = *data++;
        size |= (cmd & ~0x80) << i;
        i += 7;
    } while (cmd & 0x80 && data < top);
    *datap = data;
    return size;
}

#endif

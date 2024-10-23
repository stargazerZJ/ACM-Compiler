#define bool _Bool

#ifdef HOST
typedef unsigned long size_t;
#else
typedef unsigned size_t;
#endif

// Necessary functions in libc
int printf(const char *pattern, ...);
int sprintf(char *dest, const char *pattern, ...);
int scanf(const char *pattern, ...);
int sscanf(const char *src, const char *pattern, ...);
size_t strlen(const char *str);
int strcmp(const char *s1, const char *s2);
void *memcpy(void *dest, const void *src, size_t n);
void *malloc(size_t n);

void print(char *str) {
	printf("%s", str);
}

void println(char *str) {
	printf("%s\n", str);
}

void printInt(int n) {
	printf("%d", n);
}

void printlnInt(int n) {
	printf("%d\n", n);
}

char *getString() {
	char *buffer = malloc(4096);
	scanf("%s", buffer);
	return buffer;
}

int getInt() {
	int n;
	scanf("%d", &n);
	return n;
}

char *toString(int n) {
	char *buffer = malloc(16);
	sprintf(buffer, "%d", n);
	return buffer;
}

size_t string_length(char *__this) {
	return strlen(__this);
}

char *string_substring(char *__this, int left, int right) {
	int length = right - left;
	char *buffer = malloc(length + 1);
	memcpy(buffer, __this + left, length);
	buffer[length] = '\0';
	return buffer;
}

int string_parseInt(char *__this) {
	int n;
	sscanf(__this, "%d", &n);
	return n;
}

int string_ord(char *__this, int pos) {
	return __this[pos];
}

char *string_add(char *str1, char *str2) {
	int length1 = strlen(str1);
	int length2 = strlen(str2);
	int length = length1 + length2;
	char *buffer = malloc(length + 1);
	memcpy(buffer, str1, length1);
	memcpy(buffer + length1, str2, length2);
	buffer[length] = '\0';
	return buffer;
}

void *__new_1d_array__(int size, int elem_size) {
    return malloc(size * elem_size);
}

void *__new_int_1d_array__(int size) {
    return __new_1d_array__(size, 4);  // sizeof(int) == 4
}

void *__new_bool_1d_array__(int size) {
    return __new_1d_array__(size, 1);  // sizeof(bool) == 1
}

void *__new_ptr_1d_array__(int size) {
#ifdef HOST
    return __new_1d_array__(size, 8);  // sizeof(void*) == 8 on 64-bit
#else
    return __new_1d_array__(size, 4);  // sizeof(void*) == 4 on 32-bit
#endif
}

void *__new_arr_ptr_1d_array__(int size) {
#ifdef HOST
    return __new_1d_array__(size, 16); // sizeof(array_ptr) == 16 (ptr + length)
#else
    return __new_1d_array__(size, 8);  // sizeof(array_ptr) == 8 on 32-bit
#endif
}

void *__new_2d_array__(int size, int size2, int elem_size) {
    // Calculate total size needed
    size_t header_size = size * 2 * sizeof(size_t);  // For storing pointers and lengths
    size_t data_size = size * size2 * elem_size;     // For all secondary arrays

    // Allocate one contiguous block
    char *block = malloc(header_size + data_size);

    // Setup header array (array of pointers and lengths)
    size_t *array = (size_t*)block;
    char *data = block + header_size;

    // Initialize pointers and lengths
    for (int i = 0; i < size * 2; i += 2) {
        array[i] = (size_t)(data + (i/2) * size2 * elem_size); // Point to appropriate section
        array[i + 1] = size2;                                  // Store length
    }

    return array;
}

void *__new_int_2d_array__(int size, int size2) {
    return __new_2d_array__(size, size2, 4);  // sizeof(int) == 4
}

void *__new_bool_2d_array__(int size, int size2) {
    return __new_2d_array__(size, size2, 1);  // sizeof(bool) == 1
}

void *__new_ptr_2d_array__(int size, int size2) {
#ifdef HOST
    return __new_2d_array__(size, size2, 8);  // sizeof(void*) == 8 on 64-bit
#else
    return __new_2d_array__(size, size2, 4);  // sizeof(void*) == 4 on 32-bit
#endif
}

void *__new_arr_ptr_2d_array__(int size, int size2) {
#ifdef HOST
    return __new_2d_array__(size, size2, 16); // sizeof(array_ptr) == 16
#else
    return __new_2d_array__(size, size2, 8);  // sizeof(array_ptr) == 8 on 32-bit
#endif
}
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

void *__new_int_1d_array__(int size) {
	return malloc(size << 2);
}

void *__new_bool_1d_array__(int size) {
	return malloc(size << 1);
}

void *__new_ptr_1d_array__(int size) {
#ifdef HOST
	int *array = malloc(size << 3);
#else
	int *array = malloc(size << 2);
#endif
	return array;
}

void *__new_arr_ptr_1d_array__(int size) {
#ifdef HOST
	int *array = malloc(size << 4);
#else
	int *array = malloc(size << 3);
#endif
	return array;
}

void *__new_2d_array__(int size, int size2, void *(*__new_1d_array__)(int)) {
    size_t *array = __new_arr_ptr_1d_array__(size);
    for (int i = 0; i < size; i += 2) {
        array[i] = (size_t)__new_1d_array__(size2); // actual type is void *
        array[i + 1] = size2;   // length
    }
    return array;
}

void *__new_int_2d_array__(int size, int size2) {
	return __new_2d_array__(size, size2, __new_int_1d_array__);
}

void *__new_bool_2d_array__(int size, int size2) {
	return __new_2d_array__(size, size2, __new_bool_1d_array__);
}

void *__new_ptr_2d_array__(int size, int size2) {
	return __new_2d_array__(size, size2, __new_ptr_1d_array__);
}

void *__new_arr_ptr_2d_array__(int size, int size2) {
	return __new_2d_array__(size, size2, __new_arr_ptr_1d_array__);
}
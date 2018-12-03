cmake_minimum_required(VERSION 3.12)
project(mobileconnd C)

set(CMAKE_C_STANDARD 11)

add_compile_options(-Wall -Wextra -pedantic)

add_executable(mobileconnd mobileconnd.c)

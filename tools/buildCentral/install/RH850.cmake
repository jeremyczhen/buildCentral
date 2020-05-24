# This is a platform definition file for platforms without
# operating system, typically embedded platforms.
# It is used when CMAKE_SYSTEM_NAME is set to "Generic"
#
# It is intentionally empty, since nothing is known
# about the platform. So everything has to be specified
# in the system/compiler files ${CMAKE_SYSTEM_NAME}-<compiler_basename>.cmake
# and/or ${CMAKE_SYSTEM_NAME}-<compiler_basename>-${CMAKE_SYSTEM_PROCESSOR}.cmake

# (embedded) targets without operating system usually don't support shared libraries
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS FALSE)

# To help the find_xxx() commands, set at least the following so CMAKE_FIND_ROOT_PATH
# works at least for some simple cases:

#set(CMAKE_CXX_LINK_EXECUTABLE  "<CMAKE_CXX_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET>  <LINK_LIBRARIES>")
set(CMAKE_C_LINK_EXECUTABLE    "<CMAKE_C_COMPILER> <CMAKE_C_LINK_FLAGS>   <LINK_FLAGS> <OBJECTS> -o <TARGET>  <LINK_LIBRARIES>")
#set(CMAKE_C_CREATE_STATIC_LIBRARY "<CMAKE_AR> <TARGET> --create <LINK_FLAGS> <OBJECTS> ")


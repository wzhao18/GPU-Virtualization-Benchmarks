target_include_directories(PAIR PRIVATE ${CMAKE_CURRENT_LIST_DIR})

add_subdirectory(spmv)
add_subdirectory(sgemm)
add_subdirectory(cutcp)
add_subdirectory(mri-q)
add_subdirectory(tpacf)
add_subdirectory(lbm)
add_subdirectory(sad)
add_subdirectory(stencil)


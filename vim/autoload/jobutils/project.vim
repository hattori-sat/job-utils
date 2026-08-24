"""Small Vim-only helpers for locating a CMake project."""

function! s:directory() abort
  let l:current = expand('%:p')
  return empty(l:current) ? getcwd() : fnamemodify(l:current, ':h')
endfunction

function! jobutils#project#root() abort
  let l:cmake = findfile('CMakeLists.txt', s:directory() . ';')
  return empty(l:cmake) ? '' : fnamemodify(l:cmake, ':p:h')
endfunction

function! jobutils#project#show_root() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  echo 'CMake project: ' . l:root
endfunction

function! jobutils#project#open_cmake() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  execute 'botright split ' . fnameescape(l:root . '/CMakeLists.txt')
endfunction

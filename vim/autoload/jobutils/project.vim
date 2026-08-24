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

function! s:build_directory(root) abort
  return fnamemodify(a:root . '/build', ':p')
endfunction

function! s:run(title, command, directory) abort
  if !executable(split(a:command)[0])
    echoerr 'JobUtils: executable not found: ' . split(a:command)[0]
    return
  endif
  let l:previous_directory = getcwd()
  let l:previous_global_directory = getcwd(-1)
  let l:previous_tab_directory = getcwd(-1, 0)
  let l:previous_scope = haslocaldir()
  let l:output = ''
  let l:exit_code = 1
  try
    execute 'noautocmd keepjumps lcd ' . fnameescape(a:directory)
    let l:output = system(a:command . ' 2>&1')
    let l:exit_code = v:shell_error
  finally
    if l:previous_scope == 0
      execute 'noautocmd keepjumps cd ' . fnameescape(l:previous_global_directory)
    elseif l:previous_scope == 1
      execute 'noautocmd keepjumps lcd ' . fnameescape(l:previous_directory)
    else
      " :cd clears the temporary window scope; :tcd then restores the
      " original tab scope without changing the saved global directory.
      execute 'noautocmd keepjumps cd ' . fnameescape(l:previous_global_directory)
      execute 'noautocmd keepjumps tcd ' . fnameescape(l:previous_tab_directory)
    endif
  endtry
  let l:lines = split(l:output, '\n', 1)
  call setqflist([], 'r', {'title': a:title, 'lines': l:lines})
  if !empty(l:lines)
    copen
  endif
  if l:exit_code != 0
    echoerr 'JobUtils: ' . a:title . ' failed'
    return
  endif
  echo 'JobUtils: ' . a:title . ' completed'
endfunction

function! jobutils#project#configure() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  let l:build = s:build_directory(l:root)
  call s:run('CMake configure',
        \ 'cmake -S ' . shellescape(l:root) . ' -B ' . shellescape(l:build),
        \ l:root)
endfunction

function! jobutils#project#build() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  let l:build = s:build_directory(l:root)
  if !isdirectory(l:build)
    echoerr 'JobUtils: build directory is missing; run :JobutilsCMakeConfigure'
    return
  endif
  call s:run('CMake build', 'cmake --build ' . shellescape(l:build), l:root)
endfunction

function! jobutils#project#test() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  let l:build = s:build_directory(l:root)
  if !isdirectory(l:build)
    echoerr 'JobUtils: build directory is missing; run :JobutilsCMakeConfigure'
    return
  endif
  call s:run('CTest', 'ctest --test-dir ' . shellescape(l:build)
        \ . ' --output-on-failure', l:root)
endfunction

function! jobutils#project#make() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  call s:run('Make', 'make', l:root)
endfunction

function! jobutils#project#format_current() abort
  if &filetype !=# 'c' && &filetype !=# 'cpp'
    echoerr 'JobUtils: clang-format is available for C and C++ buffers only'
    return
  endif
  if !executable('clang-format')
    echoerr 'JobUtils: executable not found: clang-format'
    return
  endif
  let l:output = system('clang-format', join(getline(1, '$'), "\n"))
  if v:shell_error != 0
    echoerr 'JobUtils: clang-format failed'
    return
  endif
  let l:lines = split(l:output, '\n', 1)
  if !empty(l:output) && !empty(l:lines) && empty(l:lines[-1])
    call remove(l:lines, -1)
  endif
  call setline(1, l:lines)
  if line('$') > len(l:lines)
    execute (len(l:lines) + 1) . ',$delete _'
  endif
  echo 'JobUtils: clang-format completed'
endfunction

function! jobutils#project#open_compile_commands() abort
  let l:root = jobutils#project#root()
  if empty(l:root)
    echoerr 'JobUtils: CMakeLists.txt was not found from the current file'
    return
  endif
  for l:path in [l:root . '/compile_commands.json', s:build_directory(l:root) . '/compile_commands.json']
    if filereadable(l:path)
      execute 'edit ' . fnameescape(l:path)
      return
    endif
  endfor
  echoerr 'JobUtils: compile_commands.json was not found'
endfunction

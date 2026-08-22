function! s:repo_root() abort
  let l:current = expand('%:p')
  let l:directory = empty(l:current) ? getcwd() : fnamemodify(l:current, ':h')
  let l:gtd = findfile('gtd.md', l:directory . ';')
  if empty(l:gtd)
    return ''
  endif
  return fnamemodify(l:gtd, ':p:h')
endfunction

function! s:python_command() abort
  return get(g:, 'jobutils_python', has('win32') ? 'python' : 'python3')
endfunction

function! s:run(args) abort
  let l:root = s:repo_root()
  if empty(l:root)
    echoerr 'GTD: gtd.md was not found from the current file'
    return {'ok': 0, 'output': ''}
  endif
  let l:command = shellescape(s:python_command()) . ' -m jobutils ' . a:args
        \ . ' --repo ' . shellescape(l:root)
        \ . ' --gtd-file ' . shellescape(l:root . '/gtd.md')
  let l:output = system(l:command)
  return {'ok': v:shell_error == 0, 'output': l:output}
endfunction

function! s:show_error(output, fallback) abort
  echoerr a:fallback
  for l:line in split(a:output, '\n')
    if !empty(l:line) && l:line !~# '^GTD: '
      echom l:line
    endif
  endfor
endfunction

function! jobutils#gtd#dispatch() abort
  update
  let l:result = s:run('gtd dispatch')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: dispatch failed')
    return
  endif
  checktime
  echo 'GTD: dispatch done'
endfunction

function! jobutils#gtd#task() abort
  update
  let l:line = line('.')
  let l:result = s:run('gtd task --line ' . l:line)
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: task failed')
    return
  endif
  let l:path = substitute(split(l:result.output, '\n')[0], '\n\+$', '', '')
  if empty(l:path) || !filereadable(l:path)
    echoerr 'GTD: task path was not returned'
    return
  endif
  execute 'hide edit ' . fnameescape(l:path)
endfunction

function! jobutils#gtd#follow_link() abort
  let l:match = matchlist(getline('.'), '<\([^<>]\+\.md\)>')
  if empty(l:match)
    normal! gf
    return
  endif
  let l:path = fnamemodify(expand('%:p'), ':h') . '/' . l:match[1]
  if !filereadable(l:path)
    echoerr 'GTD: linked detail file is missing: ' . l:match[1]
    return
  endif
  execute 'hide edit ' . fnameescape(l:path)
endfunction

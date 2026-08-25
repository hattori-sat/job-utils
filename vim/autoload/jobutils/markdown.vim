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

function! s:show_error(output) abort
  echoerr 'GTD: paste image failed'
  for l:line in split(a:output, '\n')
    if !empty(l:line)
      echom l:line
    endif
  endfor
endfunction

function! jobutils#markdown#format() abort
  if &filetype !=# 'markdown'
    echoerr 'GTD: Markdown format requires a Markdown buffer'
    return
  endif
  let l:file = expand('%:p')
  if empty(l:file)
    echoerr 'GTD: Markdown format requires a saved file'
    return
  endif
  update
  let l:command = shellescape(s:python_command()) . ' -m jobutils markdown format'
         . ' --path ' . shellescape(l:file)
  let l:output = system(l:command)
  if v:shell_error != 0
    echoerr 'GTD: Markdown format failed'
    for l:line in split(l:output, '\n')
      if !empty(l:line)
        echom l:line
      endif
    endfor
    return
  endif
  checktime
  echo 'GTD: Markdown formatted'
endfunction

function! jobutils#markdown#paste_image(alt_text) abort
  if &filetype !=# 'markdown'
    echoerr 'GTD: paste image requires a Markdown buffer'
    return
  endif
  let l:file = expand('%:p')
  if empty(l:file)
    echoerr 'GTD: paste image requires a saved Markdown file'
    return
  endif
  let l:root = s:repo_root()
  if empty(l:root)
    echoerr 'GTD: gtd.md was not found from the current file'
    return
  endif

  update
  let l:provider = get(g:, 'jobutils_image_provider', 'auto')
  let l:command = shellescape(s:python_command()) . ' -m jobutils markdown paste-image'
        \ . ' --repo ' . shellescape(l:root)
        \ . ' --file ' . shellescape(l:file)
        \ . ' --provider ' . shellescape(l:provider)
  if !empty(a:alt_text)
    let l:command .= ' --name ' . shellescape(a:alt_text)
  endif
  let l:output = system(l:command)
  if v:shell_error != 0
    call s:show_error(l:output)
    return
  endif

  let l:link = ''
  for l:line in split(l:output, '\n')
    if l:line =~# '^markdown: '
      let l:link = substitute(l:line, '^markdown: ', '', '')
      break
    endif
  endfor
  if empty(l:link)
    call s:show_error('IMAGE: paste command returned no Markdown link')
    return
  endif

  call append(line('.'), [l:link])
  call cursor(line('.') + 1, 1)
  update
  echo 'GTD: image pasted'
endfunction

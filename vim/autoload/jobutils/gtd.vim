function! s:repo_root() abort
  let l:current = expand('%:p')
  let l:directory = empty(l:current) ? getcwd() : fnamemodify(l:current, ':h')
  let l:gtd = findfile('gtd.md', l:directory . ';')
  if empty(l:gtd)
    return ''
  endif
  return fnamemodify(l:gtd, ':p:h')
endfunction

function! s:document_root() abort
  let l:current = expand('%:p')
  let l:directory = empty(l:current) ? getcwd() : fnamemodify(l:current, ':h')
  let l:docs = findfile('docs.md', l:directory . ';')
  if empty(l:docs)
    return ''
  endif
  return fnamemodify(l:docs, ':p:h')
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

function! s:run_cli(args) abort
  let l:root = s:repo_root()
  if empty(l:root)
    return {'ok': 0, 'output': 'GTD: gtd.md was not found from the current file'}
  endif
  let l:command = shellescape(s:python_command()) . ' -m jobutils ' . a:args
        \ . ' --repo ' . shellescape(l:root)
  let l:output = system(l:command)
  return {'ok': v:shell_error == 0, 'output': l:output}
endfunction

function! s:run_metrics(args) abort
  let l:root = s:repo_root()
  if empty(l:root)
    return {'ok': 0, 'output': 'GTD: gtd.md was not found from the current file'}
  endif
  let l:command = shellescape(s:python_command()) . ' -m jobutils metrics ' . a:args
        \ . ' --repo ' . shellescape(l:root)
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

function! s:show_output(output) abort
  for l:line in split(a:output, '\n')
    if !empty(l:line)
      echom l:line
    endif
  endfor
endfunction

function! s:confirm_sync(prompt, accepted) abort
  if exists('g:jobutils_sync_confirm')
    let l:answer = g:jobutils_sync_confirm
  else
    let l:answer = input(a:prompt)
  endif
  return toupper(strpart(substitute(l:answer, '^\s*', '', ''), 0, 1)) ==# a:accepted
endfunction

function! s:sync_plan_path(root, requested) abort
  let l:plan_root = resolve(fnamemodify(a:root . '/.jobutils/sync/plans', ':p'))
  let l:plan_prefix = substitute(l:plan_root, '[\\/]\+$', '', '') . '/'
  if !empty(a:requested)
    let l:requested_path = filereadable(a:requested)
          \ ? a:requested
          \ : a:root . '/' . a:requested
    if !filereadable(l:requested_path)
      return ''
    endif
    let l:candidate = resolve(fnamemodify(l:requested_path, ':p'))
    let l:left = substitute(l:candidate, '\\', '/', 'g')
    let l:right = substitute(l:plan_prefix, '\\', '/', 'g')
    if has('win32')
      let l:left = tolower(l:left)
      let l:right = tolower(l:right)
    endif
    return stridx(l:left, l:right) == 0 ? l:candidate : ''
  endif
  let l:status = s:run_cli('sync status')
  if !l:status.ok
    return ''
  endif
  let l:latest = matchstr(l:status.output, '"latest_plan"\s*:\s*"\zs[^"]*')
  if empty(l:latest)
    return ''
  endif
  let l:candidate = a:root . '/' . substitute(l:latest, '\\', '/', 'g')
  return filereadable(l:candidate) ? resolve(fnamemodify(l:candidate, ':p')) : ''
endfunction

function! s:current_item_title() abort
  let l:line = getline('.')
  if l:line !~# '^\s*-\s*[A-Za-z0-9_-]\+:'
    return ''
  endif
  let l:title = substitute(l:line, '^\s*-\s*[A-Za-z0-9_-]\+:\s*', '', '')
  return substitute(l:title, '\s\+<[^<>]\+\.md>\s*$', '', '')
endfunction

function! s:reload_current_buffer() abort
  if &buftype ==# ''
    silent! edit!
  endif
endfunction

function! s:reload_and_restore_item(title) abort
  call s:reload_current_buffer()
  if empty(a:title)
    return
  endif
  let l:pattern = '\V' . escape(a:title, '\')
  let l:found = search(l:pattern, 'W')
  if !l:found
    call cursor(1, 1)
    call search(l:pattern, 'W')
  endif
endfunction

function! jobutils#gtd#dispatch() abort
  let l:title = s:current_item_title()
  update
  let l:result = s:run('gtd dispatch')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: dispatch failed')
    return
  endif
  call s:reload_and_restore_item(l:title)
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
  call s:reload_current_buffer()
  execute 'hide edit ' . fnameescape(l:path)
endfunction

function! s:current_task_path() abort
  let l:root = resolve(s:repo_root())
  let l:current = resolve(expand('%:p'))
  if empty(l:root) || empty(l:current)
    return ''
  endif
  let l:root = substitute(l:root, '/$', '', '')
  let l:task_prefix = l:root . '/gtd_tasks/'
  if stridx(l:current, l:task_prefix) != 0
    return ''
  endif
  return substitute(strpart(l:current, strlen(l:root) + 1), '\\', '/', 'g')
endfunction

function! s:in_subtasks_section() abort
  let l:inside = 0
  for l:index in range(1, line('.'))
    let l:heading = getline(l:index)
    if l:heading =~# '^#\s\+Subtasks\s*$'
      let l:inside = 1
    elseif l:heading =~# '^#\s\+' && l:inside
      let l:inside = 0
    endif
  endfor
  return l:inside
endfunction

function! jobutils#gtd#subtask() abort
  let l:parent = s:current_task_path()
  if empty(l:parent)
    echoerr 'GTD: subtask must be created from a task Markdown file'
    return
  endif
  if !s:in_subtasks_section()
    echoerr 'GTD: place the cursor under the # Subtasks heading'
    return
  endif
  update
  let l:line = line('.')
  let l:result = s:run_cli(
        \ 'gtd subtask --line ' . l:line . ' --parent ' . shellescape(l:parent)
        \ )
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: subtask failed')
    return
  endif
  let l:path = substitute(split(l:result.output, '\n')[0], '\n\+$', '', '')
  if empty(l:path) || !filereadable(l:path)
    echoerr 'GTD: subtask path was not returned'
    return
  endif
  call s:reload_current_buffer()
  execute 'hide edit ' . fnameescape(l:path)
endfunction
function! jobutils#gtd#document() abort
  update
  let l:root = s:document_root()
  if empty(l:root)
    echoerr 'GTD: docs.md was not found from the current file'
    return
  endif
  let l:command = shellescape(s:python_command()) . ' -m jobutils gtd document'
        \ . ' --repo ' . shellescape(l:root)
        \ . ' --docs-file ' . shellescape(l:root . '/docs.md')
        \ . ' --line ' . line('.')
  let l:output = system(l:command)
  if v:shell_error != 0
    call s:show_error(l:output, 'GTD: document failed')
    return
  endif
  let l:path = substitute(split(l:output, '\n')[0], '\n\+$', '', '')
  if empty(l:path) || !filereadable(l:path)
    echoerr 'GTD: document path was not returned'
    return
  endif
  call s:reload_current_buffer()
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

function! jobutils#gtd#catalog() abort
  let l:result = s:run_metrics('catalog')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: metrics catalog failed')
    return
  endif
  for l:line in split(l:result.output, '\n')
    if !empty(l:line)
      echom l:line
    endif
  endfor
  echo 'GTD: catalog displayed in :messages'
endfunction

function! jobutils#gtd#metrics_help() abort
  echo ':GtdReview  show the current-year task time summary'
  echo ':GtdTags    show the standard tag catalog'
  echo ':GtdImpactLevels  show impact levels'
  echo ':GtdMetricsHelp  show these commands'
endfunction

function! jobutils#gtd#review() abort
  let l:result = s:run_metrics('review')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: review failed')
    return
  endif
  for l:line in split(l:result.output, '\n')
    if !empty(l:line)
      echom l:line
    endif
  endfor
  echo 'GTD: review displayed in :messages'
endfunction

function! jobutils#gtd#sync_plan() abort
  let l:result = s:run_cli('sync plan')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: sync plan failed')
    return
  endif
  call s:show_output(l:result.output)
  echo 'GTD: sync plan created; review the JSON plan before applying it'
endfunction

function! jobutils#gtd#sync_apply(plan) abort
  let l:root = s:repo_root()
  if empty(l:root)
    echoerr 'GTD: gtd.md was not found from the current file'
    return
  endif
  let l:plan = s:sync_plan_path(l:root, a:plan)
  if empty(l:plan)
    echoerr 'GTD: no synchronization plan was found'
    return
  endif
  let l:display_plan = substitute(strpart(l:plan, strlen(l:root) + 1), '\\', '/', 'g')
  if !s:confirm_sync('Apply sync plan [' . l:display_plan . ']? (A)pply/(C)ancel: ', 'A')
    echom 'GTD: sync apply cancelled'
    return
  endif
  let l:result = s:run_cli(
        \ 'sync apply --plan ' . shellescape(l:plan) . ' --adapter atlassian'
        \ )
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: sync apply failed')
    return
  endif
  call s:show_output(l:result.output)
  echo 'GTD: sync apply completed'
endfunction

function! jobutils#gtd#sync_pull() abort
  if !s:confirm_sync('Pull external changes? (Y)es/(N)o: ', 'Y')
    echom 'GTD: sync pull cancelled'
    return
  endif
  let l:result = s:run_cli('sync pull --adapter atlassian')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: sync pull failed')
    return
  endif
  call s:show_output(l:result.output)
  echo 'GTD: sync pull completed'
endfunction

function! jobutils#gtd#sync_status() abort
  let l:result = s:run_cli('sync status')
  if !l:result.ok
    call s:show_error(l:result.output, 'GTD: sync status failed')
    return
  endif
  call s:show_output(l:result.output)
  echo 'GTD: sync status displayed in :messages'
endfunction

function! jobutils#gtd#sync_help() abort
  echo ':GtdSyncPlan              create a reviewable synchronization plan'
  echo ':GtdSyncApply [plan]      apply the newest or named plan after confirmation'
  echo ':GtdSyncPull              pull external changes after confirmation'
  echo ':GtdSyncStatus            show local plans, bases, pending actions, conflicts'
  echo ':GtdSyncHelp              show synchronization commands'
endfunction

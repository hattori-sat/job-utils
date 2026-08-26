if exists('g:loaded_jobutils_defaults')
  finish
endif
let g:loaded_jobutils_defaults = 1

if get(g:, 'jobutils_enable_filetype_defaults', 1)
  " Use Vim's built-in filename detection, syntax files, plugins, and indent
  " scripts. This covers Markdown, JSON, XML, C/C++, CMake, and Makefiles.
  filetype plugin indent on
  syntax enable
endif
if get(g:, 'jobutils_enable_defaults', 1)
  set number
  set cursorline
  set ruler
  set hidden
  set backspace=indent,eol,start
  set autoindent
  set expandtab
  set tabstop=4
  set softtabstop=4
  set shiftwidth=4
  set list
  set listchars=tab:>-,trail:.,extends:>,precedes:<
  set wildmenu
  set incsearch
  set hlsearch
  set ignorecase
  set smartcase
  set splitbelow
  set splitright
  set scrolloff=3
  if has('termguicolors')
    set termguicolors
  endif
endif

if get(g:, 'jobutils_enable_swap_defaults', 1)
  if has('win32') || has('win64')
    let s:jobutils_swap_directory = !empty($LOCALAPPDATA)
          \ ? expand('$LOCALAPPDATA') . '/vim/swap'
          \ : expand('~/vim/swap')
  elseif !empty($XDG_STATE_HOME)
    let s:jobutils_swap_directory = expand('$XDG_STATE_HOME') . '/vim/swap'
  else
    let s:jobutils_swap_directory = expand('~/.vim/swap')
  endif
  if !isdirectory(s:jobutils_swap_directory)
    silent! call mkdir(s:jobutils_swap_directory, 'p', 0700)
  endif
  if isdirectory(s:jobutils_swap_directory)
    execute 'set directory^=' . fnameescape(s:jobutils_swap_directory . '//')
  endif
endif

if get(g:, 'jobutils_enable_filetype_defaults', 1)
  augroup jobutils_filetype_defaults
    autocmd!
    " The built-in Markdown syntax marks snake_case underscores as errors.
    autocmd Syntax markdown highlight! link markdownError Normal
    autocmd FileType markdown setlocal expandtab tabstop=2 softtabstop=2 shiftwidth=2
          \ formatoptions+=croln
          \ comments=b:*,b:-,b:+,n:>
    autocmd FileType markdown let &l:formatlistpat = '^\s*\%([0-9]\+\.\|[-*+]\)\s\+'
    autocmd FileType json,xml setlocal expandtab tabstop=2 softtabstop=2 shiftwidth=2
    autocmd FileType c,cpp,cmake setlocal expandtab tabstop=4 softtabstop=4 shiftwidth=4
    " Make recipes require literal tab characters; never expand them here.
    autocmd FileType make setlocal noexpandtab tabstop=8 softtabstop=0 shiftwidth=8
  augroup END
endif
command! JobutilsCMake call jobutils#project#open_cmake()
command! JobutilsProjectRoot call jobutils#project#show_root()
command! JobutilsCMakeConfigure call jobutils#project#configure()
command! JobutilsCMakeBuild call jobutils#project#build()
command! JobutilsCMakeTest call jobutils#project#test()
command! JobutilsMake call jobutils#project#make()
command! JobutilsClangFormat call jobutils#project#format_current()
command! JobutilsCompileCommands call jobutils#project#open_compile_commands()
command! JobutilsQuickfix copen

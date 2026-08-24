" Vim syntax file
" Language: BitBake / Yocto recipe metadata

if exists('b:current_syntax')
  finish
endif

" Prefer a syntax file supplied by Vim or another runtime when available.
" This file remains a fallback for older Vim installations.
let s:syntax_files = split(globpath(&runtimepath, 'syntax/bitbake.vim', 1), '\n')
if len(s:syntax_files) > 1
  execute 'source ' . fnameescape(s:syntax_files[-1])
  unlet s:syntax_files
  finish
endif
unlet s:syntax_files

syn case match
syn keyword bitbakeDirective inherit include require export unset addtask
syn keyword bitbakeDirective python fakeroot network nostamp cleandirs
syn keyword bitbakeVariable PN PV PR SRC_URI SRCREV S SRC_DIR FILESEXTRAPATHS
syn keyword bitbakeVariable DEPENDS RDEPENDS RRECOMMENDS PROVIDES PACKAGES
syn keyword bitbakeVariable do_fetch do_unpack do_patch do_configure do_compile
syn keyword bitbakeVariable do_install do_package do_deploy
syn match bitbakeTask "\<do_[A-Za-z0-9_+-]\+\>"
syn match bitbakeFlag "\<\(append\|prepend\|remove\|class-native\|class-nativesdk\)\>"
syn match bitbakeOperator "\([?]=\|+=\|\.=\|=+\|=\.\|=\)"
syn match bitbakeVariableRef "${[^}]*}"
syn match bitbakePythonFunction "^[ 	]*def[ 	]\+[A-Za-z_][A-Za-z0-9_]*"
syn match bitbakeShellFunction "^[ 	]*[A-Za-z0-9_+-]\+[ 	]*()[ 	]*{" contains=bitbakeTask
syn match bitbakeComment "#.*$" contains=bitbakeTodo
syn keyword bitbakeTodo TODO FIXME NOTE XXX contained

hi def link bitbakeDirective Statement
hi def link bitbakeVariable Identifier
hi def link bitbakeTask Function
hi def link bitbakeFlag Type
hi def link bitbakeOperator Operator
hi def link bitbakeVariableRef Special
hi def link bitbakePythonFunction Function
hi def link bitbakeShellFunction Function
hi def link bitbakeComment Comment
hi def link bitbakeTodo Todo

let b:jobutils_bitbake_fallback = 1
let b:current_syntax = 'bitbake'

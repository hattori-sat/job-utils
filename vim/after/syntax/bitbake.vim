" Small additions for Vim installations with an existing BitBake syntax.
if exists('b:jobutils_bitbake_fallback')
  finish
endif

syn case match
syn match jobutilsBitbakeTask "\<do_[A-Za-z0-9_+-]\+\>"
syn match jobutilsBitbakeVariableRef "${[^}]*}"

hi def link jobutilsBitbakeTask Function
hi def link jobutilsBitbakeVariableRef Special

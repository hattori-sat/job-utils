if exists('g:loaded_jobutils_markdown')
  finish
endif
let g:loaded_jobutils_markdown = 1

command! -nargs=* PasteImage call jobutils#markdown#paste_image(<q-args>)
command! GtdFormat call jobutils#markdown#format()

cnoreabbrev <expr> pasteimage
      \ getcmdtype() ==# ':' && getcmdline() =~# '^pasteimage\%([[:space:]]\|$\)' ? 'PasteImage' : 'pasteimage'
cnoreabbrev <expr> gtdformat
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdformat' ? 'GtdFormat' : 'gtdformat'

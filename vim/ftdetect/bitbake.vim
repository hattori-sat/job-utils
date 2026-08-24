" Detect common Yocto/OpenEmbedded recipe and class files.
if exists('did_load_filetypes')
  finish
endif

augroup filetypedetect
  autocmd BufRead,BufNewFile *.bb,*.bbappend,*.bbclass setf bitbake
  autocmd BufRead,BufNewFile */recipes-*/*.inc setf bitbake
  autocmd BufRead,BufNewFile */conf/*.conf setf bitbake
augroup END

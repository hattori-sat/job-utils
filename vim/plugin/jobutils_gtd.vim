if exists('g:loaded_jobutils_gtd')
  finish
endif
let g:loaded_jobutils_gtd = 1

command! Gtd call jobutils#gtd#dispatch()
command! GtdTask call jobutils#gtd#task()
command! GtdTags call jobutils#gtd#catalog()
command! GtdImpactLevels call jobutils#gtd#catalog()
command! GtdMetricsHelp call jobutils#gtd#metrics_help()
command! GtdReview call jobutils#gtd#review()

augroup jobutils_gtd_detail_links
  autocmd!
  autocmd BufRead,BufNewFile gtd.md nnoremap <buffer><silent> gf :<C-U>call jobutils#gtd#follow_link()<CR>
augroup END

" Keep the original lowercase muscle-memory commands available.
cnoreabbrev <expr> gtd
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtd' ? 'Gtd' : 'gtd'
cnoreabbrev <expr> gtdtask
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdtask' ? 'GtdTask' : 'gtdtask'

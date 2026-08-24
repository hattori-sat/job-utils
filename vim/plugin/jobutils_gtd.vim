if exists('g:loaded_jobutils_gtd')
  finish
endif
let g:loaded_jobutils_gtd = 1

command! Gtd call jobutils#gtd#dispatch()
command! GtdTask call jobutils#gtd#task()
command! GtdSubtask call jobutils#gtd#subtask()
command! GtdDoc call jobutils#gtd#document()
command! GtdTags call jobutils#gtd#catalog()
command! GtdImpactLevels call jobutils#gtd#catalog()
command! GtdMetricsHelp call jobutils#gtd#metrics_help()
command! GtdReview call jobutils#gtd#review()
command! GtdSyncPlan call jobutils#gtd#sync_plan()
command! -nargs=? GtdSyncApply call jobutils#gtd#sync_apply(<q-args>)
command! GtdSyncPull call jobutils#gtd#sync_pull()
command! GtdSyncStatus call jobutils#gtd#sync_status()
command! GtdSyncHelp call jobutils#gtd#sync_help()

augroup jobutils_gtd_detail_links
  autocmd!
  autocmd BufRead,BufNewFile gtd.md nnoremap <buffer><silent> gf :<C-U>call jobutils#gtd#follow_link()<CR>
augroup END

" Keep the original lowercase muscle-memory commands available.
cnoreabbrev <expr> gtd
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtd' ? 'Gtd' : 'gtd'
cnoreabbrev <expr> gtdtask
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdtask' ? 'GtdTask' : 'gtdtask'
cnoreabbrev <expr> gtddoc
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtddoc' ? 'GtdDoc' : 'gtddoc'
cnoreabbrev <expr> gtdsubtask
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsubtask' ? 'GtdSubtask' : 'gtdsubtask'
cnoreabbrev <expr> gtdtags
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdtags' ? 'GtdTags' : 'gtdtags'
cnoreabbrev <expr> gtdimpactlevels
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdimpactlevels' ? 'GtdImpactLevels' : 'gtdimpactlevels'
cnoreabbrev <expr> gtdmetricshelp
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdmetricshelp' ? 'GtdMetricsHelp' : 'gtdmetricshelp'
cnoreabbrev <expr> gtdreview
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdreview' ? 'GtdReview' : 'gtdreview'
cnoreabbrev <expr> gtdsyncplan
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsyncplan' ? 'GtdSyncPlan' : 'gtdsyncplan'
cnoreabbrev <expr> gtdsyncapply
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsyncapply' ? 'GtdSyncApply' : 'gtdsyncapply'
cnoreabbrev <expr> gtdsyncpull
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsyncpull' ? 'GtdSyncPull' : 'gtdsyncpull'
cnoreabbrev <expr> gtdsyncstatus
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsyncstatus' ? 'GtdSyncStatus' : 'gtdsyncstatus'
cnoreabbrev <expr> gtdsynchelp
      \ getcmdtype() ==# ':' && getcmdline() ==# 'gtdsynchelp' ? 'GtdSyncHelp' : 'gtdsynchelp'

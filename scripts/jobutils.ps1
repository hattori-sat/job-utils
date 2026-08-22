param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Arguments
)

python -m jobutils @Arguments

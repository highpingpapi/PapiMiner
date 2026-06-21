param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

$Script = Join-Path $PSScriptRoot "PapiMiner.py"
python $Script @Args

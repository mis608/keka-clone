$html = Get-Content 'c:\Users\Sunil Kumar\keka-hrms-clone\templates\dashboard.html' -Raw
$js = Get-Content 'c:\Users\Sunil Kumar\keka-hrms-clone\static\js\app.js' -Raw

# Find all <button ...> tags
$btns = [regex]::Matches($html, '<button\b[^>]*>(.{0,80})')
foreach ($b in $btns) {
  $tag = $b.Value
  $hasOnclick = $tag -match 'onclick='
  $idm = [regex]::Match($tag, 'id="([\w-]+)"')
  $id = if ($idm.Success) { $idm.Groups[1].Value } else { '' }
  $wired = $false
  if ($hasOnclick) { $wired = $true }
  elseif ($id -and $js -like "*getElementById('$id')*") { $wired = $true }
  elseif ($tag -match 'type="submit"') { $wired = $true }
  if (-not $wired) {
    $text = ($b.Groups[1].Value -replace '<[^>]+>','' -replace '\s+',' ').Trim()
    Write-Output ("DEAD BUTTON | id=" + $id + " | text=" + $text + " | tag=" + $tag.Substring(0,[Math]::Min(140,$tag.Length)))
  }
}
Write-Output '--- button check done ---'

# Check other interactive elements: selects with onchange
$sels = [regex]::Matches($html, '<select\b[^>]*id="([\w-]+)"[^>]*>')
foreach ($s in $sels) {
  $id = $s.Groups[1].Value
  if ($s.Value -notmatch 'onchange=' -and $js -notlike "*getElementById('$id')*") {
    Write-Output ("UNWIRED SELECT: " + $id)
  }
}
Write-Output '--- select check done ---'

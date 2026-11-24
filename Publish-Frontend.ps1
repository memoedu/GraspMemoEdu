param(
    [string]$Repository = 'memoedu/GraspMemoEdu-Pages',
    [string]$ExportDirectory = 'D:\Artifacts\GraspMemoEdu\pages-ready',
    [string]$EvidenceDirectory = 'D:\Artifacts\GraspMemoEdu\publication',
    [string]$ExpectedParent = '',
    [string]$PublicationBranch = '',
    [string]$ExpectedPublicationHead = ''
)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'scripts/version_web_assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Static asset version check failed. Refresh asset URLs before export and publication.' }
if ($Repository -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$') { throw 'Invalid repository name.' }
if ($PublicationBranch -and $PublicationBranch -notmatch '^(feat|fix|docs|codex)/[A-Za-z0-9][A-Za-z0-9-]*$') {
    throw 'Invalid publication branch.'
}
if ($ExpectedPublicationHead -and (-not $PublicationBranch -or $ExpectedPublicationHead -cnotmatch '^[a-f0-9]{40}$')) {
    throw 'Updating a publication branch requires its exact previous head.'
}
$expected = @('.nojekyll','app.js','deployment.json','favicon.svg','index.html','portal.js','review.js','atomic.js','learning-cache.js','question-input.js','content-report.js','help-feedback.js','catalog-picker.js','portal.css','subjects.js','subjects.css','styles.css','i18n.js','reader-messages.js','portal-messages.js','static-messages.js','course-graph.js','course-graph.css')
$files = @(Get-ChildItem -LiteralPath $ExportDirectory -File -Force -Recurse)
$expected += @('training.js','training.css','training-messages.js','learning-ui.js')
$expected += @('beginner-hints.js')
$expected += @('math-presentation.js','math-syntax.js')
$expected += @('vendor/mathjax-svg-glyphs/index.mjs','vendor/mathjax-svg-glyphs/LICENSE')
$expected += @('review-papers.js','review-paper-messages.js')
$expected += @('review-directory.js','task-tree.js','catalog-outline.js','content-timer.js','self-assessment.js')
$expected += @('catalog-workspace.js','free-study.js')
$expected += @('topic-sync-navigation.js','topic-sync-groups.js','topic-body-editor.js','remnote-install.html')
$expected += @('clipper.js','clipper-workspace.js','clipper-library.js','clipper-selection.js','clipper-settings.js','clipper-host.js','clipper.css')
$clipper = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/clipper-assets.json') -Raw | ConvertFrom-Json -AsHashtable
$clipperRoot = 'vendor/knowledge-clipper/'
$clipperManifest = 'vendor/clipper-release.json'
$clipperAssetPattern = '^(?:_framework/|chat/(?:assets/)?|math/)?[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:html|js|mjs|css|json|txt|wasm|dat|woff2?|ttf)$'
$expected += $clipperManifest
if ((Get-Content (Join-Path $ExportDirectory $clipperManifest) -Raw).Replace("`r`n","`n") -cne (Get-Content (Join-Path $PSScriptRoot 'scripts/clipper-assets.json') -Raw).Replace("`r`n","`n")) { throw 'Exported clipper release manifest is stale.' }
$clipperDirs = @('vendor/knowledge-clipper','vendor/knowledge-clipper/_framework','vendor/knowledge-clipper/chat','vendor/knowledge-clipper/chat/assets','vendor/knowledge-clipper/math')
foreach ($name in $clipper.files.Keys) {
    if ($name -notmatch $clipperAssetPattern) { throw 'Invalid clipper release path.' }
    $relative = $clipperRoot + $name
    if ((Get-FileHash -LiteralPath (Join-Path $ExportDirectory $relative) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $clipper.files[$name]) { throw "Clipper distribution differs from upstream: $name" }
    $expected += $relative
}
$expected += @('focus-mode.js','focus-mode.css')
$expected += @('memory-chunk.js')
$expected += @('academy-messages.js','idea-setup.js')
$expected += @('hyperskill.js')
$expected += @('topic-content.js','topic-content.css','topic-callouts.css')
$expected += @('student-dashboard.js','presence.js')
$expected += @('composite-input.js')
$expected += @('restore.html','migration-source.html','origin-transfer.js')
$expected += @('response-cache.js')
$expected += @('question-tools.js','calculator.js','calculator-panel.js','calculator-inputs.js','calculator-policy.js','calculator-engine.js','calculator-worker.js','calculator.css')
$expected += @('whiteboard.js','whiteboard.css','whiteboard-archive.js','whiteboard-answer.js','whiteboard-editor.js','whiteboard-license.txt')
$expected += @('point-assessment.js','context-library.js','context-library.css','context-library-messages.js','training-audio.js')
$expected += @('microphone-recorder.js','voice-input.js','voice-stream.js','voice-pcm.js','voice-context.js','answer-conversion.js')
$expected += @('rubber-duck.js','rubber-duck-test.html')
$expected += @('autocomplete.js','autocomplete.css')
$expected += @('download.html','install.css','pwa.css','pwa.js','sw.js','manifest.webmanifest','icon-180.png','icon-192.png','icon-512.png','icon-maskable-512.png')
$pwaDirectories = @('pwa-free-study', 'pwa-math-courses')
$expected += 'pwa-location.js'
foreach ($directory in $pwaDirectories) {
    $expected += @("$directory/index.html", "$directory/install.html", "$directory/manifest.webmanifest")
}
$vendor = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/topic-presentation-assets.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($name in $vendor.files.Keys) {
    if ($name -notmatch '^vendor/(mermaid/[A-Za-z0-9_.-]+\.js|document-backlinks\.mjs)$') { throw 'Invalid vendor asset path.' }
    $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web/' + $name)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $vendor.files[$name]) { throw ('Vendor source differs from pinned build: ' + $name) }
}
$expected += @($vendor.files.Keys)
$chat = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/chat-assets.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($name in $chat.files.Keys) {
    if ($name -notmatch '^vendor/chat/(chat\.js(?:\.LEGAL\.txt)?|LICENSES\.txt|katex\.min\.css|fonts/KaTeX_[A-Za-z0-9-]+\.woff2)$') { throw 'Invalid chat asset path.' }
    $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web/' + $name)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $chat.files[$name]) { throw ('Chat source differs from pinned build: ' + $name) }
}
$expected += @($chat.files.Keys)
$bookFont = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/book-font-assets.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($name in $bookFont.files.Keys) {
    if ($name -notmatch '^vendor/book-font/([a-f0-9]{16}\.woff2|font\.css|LICENSE|sources\.json)$') { throw 'Invalid book font asset path.' }
    $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web/' + $name)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $bookFont.files[$name]) { throw ('Book font differs from pinned source: ' + $name) }
}
$expected += @($bookFont.files.Keys)
$calculator = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/calculator-assets.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($name in $calculator.files.Keys) {
    if ($name -notmatch '^vendor/calculator/((core|advanced|symbolic|applied|completion)\.mjs(\.LEGAL\.txt)?|LICENSES\.txt)$') { throw 'Invalid calculator asset path.' }
    $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web/' + $name)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $calculator.files[$name]) { throw ('Calculator source differs from pinned build: ' + $name) }
}
$expected += @($calculator.files.Keys)
$formula = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/formula-assets.json') -Raw | ConvertFrom-Json -AsHashtable
foreach ($name in $formula.files.Keys) {
    if ($name -notmatch '^vendor/formula/(editor\.mjs(?:\.LEGAL\.txt)?|previews\.mjs|LICENSES\.txt|fonts/[A-Za-z0-9_.-]+\.woff2)$') { throw 'Invalid formula asset path.' }
    $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web/' + $name)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $formula.files[$name]) { throw ('Formula source differs from pinned build: ' + $name) }
}
$expected += @('formula-input.js','formula-catalog.js','formula-input.css') + @($formula.files.Keys)
$relativeFiles = @($files | ForEach-Object { [IO.Path]::GetRelativePath($ExportDirectory, $_.FullName).Replace('\','/') })
if (@(Compare-Object ($expected | Sort-Object) ($relativeFiles | Sort-Object)).Count -ne 0) { throw 'Unexpected files in static publication directory.' }
foreach ($name in $expected | Where-Object { $_ -notin @('.nojekyll', 'deployment.json', $clipperManifest) }) {
    $sourceHash = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('web\' + $name)) -Algorithm SHA256).Hash
    $exportHash = (Get-FileHash -LiteralPath (Join-Path $ExportDirectory $name) -Algorithm SHA256).Hash
    if ($sourceHash -ne $exportHash) { throw ('Static export is stale: ' + $name) }
}
$deployment = Get-Content -LiteralPath (Join-Path $ExportDirectory 'deployment.json') -Raw | ConvertFrom-Json -AsHashtable
if (@(Compare-Object @('api_origin') @($deployment.Keys)).Count -ne 0) { throw 'Deployment configuration must contain only api_origin.' }
$apiUri = $null
if (-not [uri]::TryCreate($deployment.api_origin, [UriKind]::Absolute, [ref]$apiUri) -or
    $apiUri.Scheme -ne 'https' -or $apiUri.UserInfo -or $apiUri.Query -or $apiUri.Fragment -or
    $deployment.api_origin -ne $apiUri.GetLeftPart([UriPartial]::Authority) -or
    $deployment.api_origin -match '[\s*\\]') { throw 'Publication requires one exact HTTPS API origin without credentials or a path.' }
New-Item -Path $EvidenceDirectory -ItemType Directory -Force | Out-Null
function Invoke-Api([string]$Method, [string]$Endpoint, $Body = $null) {
    $arguments = @('api','--method',$Method,$Endpoint,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2022-11-28')
    if ($null -ne $Body) {
        $requestPath = Join-Path $EvidenceDirectory 'request.json'
        $Body | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $requestPath -Encoding utf8
        $arguments += @('--input',$requestPath)
    }
    $raw = & gh @arguments
    if ($LASTEXITCODE -ne 0) { throw ('GitHub API failed: ' + $Method + ' ' + $Endpoint) }
    if ($raw) { return ($raw | ConvertFrom-Json) }
}
$owner,$name = $Repository.Split('/')
$login = (& gh api user --jq .login).Trim()
if ($LASTEXITCODE -ne 0 -or -not $login) { throw 'An authenticated GitHub identity is required.' }
$existing = & gh repo list $owner --limit 1000 --json nameWithOwner,isPrivate | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect repository.' }
$repo = @($existing | Where-Object nameWithOwner -EQ $Repository)
$created = $repo.Count -eq 0
if ($created) {
    if ($PublicationBranch) { throw 'Create and configure Pages before preparing a publication branch.' }
    Write-Output 'Creating the authorized public frontend repository.'
    $createEndpoint = if ($owner -eq $login) { 'user/repos' } else { 'orgs/' + $owner + '/repos' }
    $info = Invoke-Api POST $createEndpoint @{name=$name;private=$false;auto_init=$true;description='GraspMemoEdu static frontend. Course data, answers and credentials remain local.'}
} else {
    if ($repo[0].isPrivate) { throw 'Refusing to change visibility of an existing private repository.' }
    # An intentional shutdown must not be undone by a routine frontend update.
    $null = & gh api ('repos/' + $Repository + '/pages') 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Pages is disabled or unavailable. Restore site availability before publishing.' }
    $info = Invoke-Api GET ('repos/' + $Repository)
}
$branch = $info.default_branch
if (-not $info.permissions.push) { throw 'The current GitHub identity needs write access to the publication repository.' }
$reference = Invoke-Api GET ('repos/' + $Repository + '/git/ref/heads/' + $branch)
$parent = $reference.object.sha
if ($ExpectedParent -and $parent -ne $ExpectedParent) { throw 'The public frontend changed during acceptance. Reconcile the new deployment before publishing.' }
$parents = @($parent)
if ($ExpectedPublicationHead) {
    $draft = Invoke-Api GET ('repos/' + $Repository + '/git/ref/heads/' + $PublicationBranch)
    if ($draft.object.sha -ne $ExpectedPublicationHead) { throw 'The publication branch changed during acceptance.' }
    $parents = @($ExpectedPublicationHead, $parent) | Select-Object -Unique
}
$commit = Invoke-Api GET ('repos/' + $Repository + '/git/commits/' + $parent)
$priorTree = Invoke-Api GET ('repos/' + $Repository + '/git/trees/' + $commit.tree.sha + '?recursive=1')
$publicationDocs = @('README.md','AGENTS.md','CONTRIBUTING.md')
# The previous tree may still contain the removed formula popover script.
# The generated tree remains constrained to the current export allowlist.
$allowedPrior = if ($created) { @('README.md') } else { $expected + $publicationDocs + @('formula-selection.js') }
$previousManifest = $priorTree.tree | Where-Object { $_.type -eq 'blob' -and $_.path -eq $clipperManifest }
if ($previousManifest) {
    $blob = Invoke-Api GET ('repos/' + $Repository + '/git/blobs/' + $previousManifest.sha)
    $priorRelease = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($blob.content)) | ConvertFrom-Json -AsHashtable
    if ($priorRelease.revision -notmatch '^[a-f0-9]{40}$' -or $priorRelease.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid previous clipper release.' }
    foreach ($name in $priorRelease.files.Keys) {
        if ($name -notmatch $clipperAssetPattern -or $priorRelease.files[$name] -notmatch '^[a-f0-9]{64}$') { throw 'Invalid previous clipper release file.' }
        $allowedPrior += $clipperRoot + $name
    }
}
$allowedDirectories = @('vendor','vendor/mermaid','vendor/chat','vendor/chat/fonts','vendor/book-font','vendor/calculator','vendor/formula','vendor/formula/fonts','vendor/mathjax-svg-glyphs') + $pwaDirectories + $clipperDirs
if ($priorTree.truncated -or @($priorTree.tree | Where-Object { ($_.type -eq 'blob' -and $_.path -notin $allowedPrior) -or ($_.type -eq 'tree' -and $_.path -notin $allowedDirectories) -or $_.type -notin @('blob','tree') }).Count) {
    throw 'Existing repository contains files outside the frontend allowlist. Publication stopped.'
}
$priorBlobs = @{}
foreach ($item in $priorTree.tree | Where-Object type -EQ 'blob') { $priorBlobs[$item.path] = $item.sha }
$knownBlobs = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($hash in $priorBlobs.Values) { $null = $knownBlobs.Add($hash) }
if ($ExpectedPublicationHead) {
    $draftCommit = Invoke-Api GET ('repos/' + $Repository + '/git/commits/' + $ExpectedPublicationHead)
    $draftTree = Invoke-Api GET ('repos/' + $Repository + '/git/trees/' + $draftCommit.tree.sha + '?recursive=1')
    foreach ($item in $draftTree.tree | Where-Object type -EQ 'blob') { $null = $knownBlobs.Add($item.sha) }
}
$exportBlobs = @{}
$treeItems = @($files | ForEach-Object {
    $entry = @{path=[IO.Path]::GetRelativePath($ExportDirectory, $_.FullName).Replace('\','/');mode='100644';type='blob'}
    $binary = $_.Extension -in @('.woff2','.woff','.ttf','.png','.wasm','.dat') -or ($entry.path.StartsWith($clipperRoot) -and $_.Length -gt 65536)
    if ($binary) {
        $bytes = [IO.File]::ReadAllBytes($_.FullName)
    } else {
        $content = [IO.File]::ReadAllText($_.FullName)
        $bytes = [Text.Encoding]::UTF8.GetBytes($content)
    }
    $digest = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA1)
    try {
        $digest.AppendData([Text.Encoding]::ASCII.GetBytes('blob ' + $bytes.Length + [char]0))
        $digest.AppendData($bytes)
        $blobHash = [Convert]::ToHexString($digest.GetHashAndReset()).ToLowerInvariant()
    } finally { $digest.Dispose() }
    $exportBlobs[$entry.path] = $blobHash
    if ($knownBlobs.Contains($blobHash)) {
        $entry.sha = $blobHash
    } elseif ($binary) {
        # Reuse a verified object after an interrupted upload.
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            & gh api ('repos/' + $Repository + '/git/blobs/' + $blobHash) --silent 2>$null
            if ($LASTEXITCODE -eq 0) { $entry.sha = $blobHash; break }
            try {
                $blob = Invoke-Api POST ('repos/' + $Repository + '/git/blobs') @{content=[Convert]::ToBase64String($bytes);encoding='base64'}
                if ($blob.sha -ne $blobHash) { throw 'Uploaded binary differs from its Git blob hash.' }
                $entry.sha = $blob.sha; break
            } catch {
                if ($attempt -eq 3) { throw }
                Start-Sleep -Seconds (2 * $attempt)
            }
        }
    } else { $entry.content = $content }
    $entry
})
foreach ($doc in $publicationDocs) {
    if ($priorBlobs.ContainsKey($doc)) { $treeItems += @{path=$doc;mode='100644';type='blob';sha=$priorBlobs[$doc]} }
}
$tree = Invoke-Api POST ('repos/' + $Repository + '/git/trees') @{tree=$treeItems}
$published = Invoke-Api POST ('repos/' + $Repository + '/git/commits') @{message='Publish verified learning frontend';tree=$tree.sha;parents=@($parents)}
$verifiedTree = Invoke-Api GET ('repos/' + $Repository + '/git/trees/' + $published.tree.sha + '?recursive=1')
$verifiedExpected = $expected + @($publicationDocs | Where-Object { $priorBlobs.ContainsKey($_) })
if ($verifiedTree.truncated -or @($verifiedTree.tree | Where-Object { $_.type -notin @('blob','tree') }).Count -or
    @(Compare-Object ($verifiedExpected | Sort-Object) (($verifiedTree.tree | Where-Object type -EQ 'blob').path | Sort-Object)).Count) {
    throw 'Remote publication tree failed the exact frontend allowlist.'
}
foreach ($item in $verifiedTree.tree | Where-Object type -EQ 'blob') {
    if ($exportBlobs.ContainsKey($item.path) -and $exportBlobs[$item.path] -cne $item.sha) {
        throw ('Remote publication content differs: ' + $item.path)
    }
}
if ($PublicationBranch) {
    if ($ExpectedPublicationHead) {
        $null = Invoke-Api PATCH ('repos/' + $Repository + '/git/refs/heads/' + $PublicationBranch) @{sha=$published.sha;force=$false}
    } else {
        $null = Invoke-Api POST ('repos/' + $Repository + '/git/refs') @{ref="refs/heads/$PublicationBranch";sha=$published.sha}
    }
    $receipt = @{repository=$Repository;branch=$PublicationBranch;commit=$published.sha;parent=$parent;status='ready_for_pull_request'}
    $receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'deployment.json') -Encoding utf8
    $receipt | ConvertTo-Json
    return
}
$null = Invoke-Api PATCH ('repos/' + $Repository + '/git/refs/heads/' + $branch) @{sha=$published.sha;force=$false}
Write-Output 'Frontend files are committed. Enabling GitHub Pages.'
$pageRaw = & gh api ('repos/' + $Repository + '/pages') 2>$null
$pageExit = $LASTEXITCODE
if ($pageExit -eq 0) {
    $pages = $pageRaw | ConvertFrom-Json
    $null = Invoke-Api PUT ('repos/' + $Repository + '/pages') @{source=@{branch=$branch;path='/'};build_type='legacy'}
} else {
    if (-not $created) { throw 'Pages became unavailable during publication. Refusing to recreate a disabled site.' }
    if (($pageRaw -join '') -notmatch '"status"\s*:\s*"404"|"message"\s*:\s*"Not Found"') { throw 'Unable to inspect Pages state.' }
    $pages = Invoke-Api POST ('repos/' + $Repository + '/pages') @{source=@{branch=$branch;path='/'};build_type='legacy'}
}
$receipt = @{repository=$Repository;visibility='public';branch=$branch;commit=$published.sha;url=$pages.html_url;api_origin=$deployment.api_origin;status='submitted';files=$expected;includes_course_data=$false}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $EvidenceDirectory 'deployment.json') -Encoding utf8
$receipt | ConvertTo-Json -Depth 5

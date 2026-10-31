# Render the supplied path-only SVG with Windows WPF; no extra build dependency.
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
$assets = Join-Path $workspace 'apps\assets'
$source = Join-Path $assets 'logo.svg'
Add-Type -AssemblyName PresentationCore,WindowsBase
[xml]$svg = [IO.File]::ReadAllText($source)
$namespaces = New-Object Xml.XmlNamespaceManager($svg.NameTable)
$namespaces.AddNamespace('svg', 'http://www.w3.org/2000/svg')
$paths = @($svg.SelectNodes('//svg:path', $namespaces))
if ($paths.Count -ne 1 -or $svg.DocumentElement.GetAttribute('viewBox') -ne '0 0 43 18') {
    throw 'This renderer expects the supplied 43 x 18 path-only logo.'
}
$geometry = [Windows.Media.Geometry]::Parse($paths[0].GetAttribute('d'))
$background = New-Object Windows.Media.SolidColorBrush([Windows.Media.ColorConverter]::ConvertFromString('#172037'))
$logoScale = 216.0 / 43.0
$logoTop = (256.0 - 18.0 * $logoScale) / 2.0
foreach ($size in @(16,20,24,32,40,48,64,128,256,512)) {
    $visual = New-Object Windows.Media.DrawingVisual
    $drawing = $visual.RenderOpen()
    $drawing.PushTransform((New-Object Windows.Media.ScaleTransform(($size / 256.0), ($size / 256.0))))
    $drawing.DrawRoundedRectangle($background, $null, (New-Object Windows.Rect(0,0,256,256)), 56, 56)
    $drawing.PushTransform((New-Object Windows.Media.TranslateTransform(20,$logoTop)))
    $drawing.PushTransform((New-Object Windows.Media.ScaleTransform($logoScale,$logoScale)))
    $drawing.PushClip((New-Object Windows.Media.RectangleGeometry((New-Object Windows.Rect(0,0,43,18)))))
    $drawing.DrawGeometry([Windows.Media.Brushes]::White, $null, $geometry)
    1..4 | ForEach-Object { $drawing.Pop() }
    $drawing.Close()
    $bitmap = New-Object Windows.Media.Imaging.RenderTargetBitmap($size,$size,96,96,[Windows.Media.PixelFormats]::Pbgra32)
    $bitmap.Render($visual)
    $encoder = New-Object Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
    $stream = [IO.File]::Create((Join-Path $assets ('app-' + $size + '.png')))
    try { $encoder.Save($stream) } finally { $stream.Dispose() }
}
# ICO embeds the individually rendered PNGs, preserving crisp small-size artwork.
$iconStream = [IO.File]::Create((Join-Path $assets 'app.ico'))
$writer = New-Object IO.BinaryWriter($iconStream)
try {
    $sizes = @(16,20,24,32,40,48,64,128,256)
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    foreach ($size in $sizes) {
        $bytes = [IO.File]::ReadAllBytes((Join-Path $assets ('app-' + $size + '.png')))
        $dimension = if ($size -eq 256) { 0 } else { $size }
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$bytes.Length); $writer.Write([uint32]$offset)
        $offset += $bytes.Length
    }
    foreach ($size in $sizes) {
        $writer.Write([IO.File]::ReadAllBytes((Join-Path $assets ('app-' + $size + '.png'))))
    }
} finally { $writer.Dispose(); $iconStream.Dispose() }
# Browser favicon uses the original vector paths with the same framing.
$svg.DocumentElement.SetAttribute('x', '20')
$svg.DocumentElement.SetAttribute('y', $logoTop.ToString([Globalization.CultureInfo]::InvariantCulture))
$svg.DocumentElement.SetAttribute('width', '216')
$svg.DocumentElement.SetAttribute('height', (18 * $logoScale).ToString([Globalization.CultureInfo]::InvariantCulture))
$favicon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" rx="56" fill="#172037"/>' + $svg.DocumentElement.OuterXml + '</svg>'
[IO.File]::WriteAllText((Join-Path $assets 'app.svg'), $favicon, (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $workspace 'apps\web\demo\favicon.svg'), $favicon, (New-Object Text.UTF8Encoding($false)))
Write-Output 'Rendered app icons from apps/assets/logo.svg.'

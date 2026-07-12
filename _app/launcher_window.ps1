param(
    [Parameter(Mandatory = $true)][string]$StatusPath,
    [Parameter(Mandatory = $true)][string]$CancelPath,
    [Parameter(Mandatory = $true)][string]$LogPath
)

$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$heroBase64 = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "launcher-hero.b64"), [System.Text.Encoding]::ASCII).Trim()
$heroBytes = [Convert]::FromBase64String($heroBase64)
$heroStream = New-Object System.IO.MemoryStream(,$heroBytes)
$heroBitmap = New-Object System.Windows.Media.Imaging.BitmapImage
$heroBitmap.BeginInit()
$heroBitmap.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
$heroBitmap.StreamSource = $heroStream
$heroBitmap.EndInit()
$heroBitmap.Freeze()
$heroStream.Dispose()

[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="EchoWraith - Luna" Width="1180" Height="760"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize"
        Background="#030817" Foreground="#F7F9FF"
        FontFamily="Segoe UI" ShowInTaskbar="True">
  <Window.Resources>
    <LinearGradientBrush x:Key="AuroraBrush" StartPoint="0,0" EndPoint="1,0">
      <GradientStop Color="#39DFFF" Offset="0"/>
      <GradientStop Color="#4F7FFF" Offset="0.45"/>
      <GradientStop Color="#A557FF" Offset="1"/>
    </LinearGradientBrush>
    <Style TargetType="Button">
      <Setter Property="Foreground" Value="#EAF0FF"/>
      <Setter Property="Background" Value="#101A39"/>
      <Setter Property="BorderBrush" Value="#30467D"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="18,10"/>
      <Setter Property="FontSize" Value="14"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border CornerRadius="10" Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>
  <Grid>
    <Grid.RowDefinitions>
      <RowDefinition Height="233"/>
      <RowDefinition Height="174"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="62"/>
    </Grid.RowDefinitions>

    <Border Grid.Row="0" CornerRadius="0,0,18,18" ClipToBounds="True">
      <Image x:Name="HeroImage" Stretch="UniformToFill"/>
    </Border>

    <Grid Grid.Row="1" Margin="28,18,28,10">
      <Grid.ColumnDefinitions>
        <ColumnDefinition Width="*"/>
        <ColumnDefinition Width="300"/>
      </Grid.ColumnDefinitions>
      <Border Grid.Column="0" CornerRadius="16" BorderBrush="#263A72" BorderThickness="1" Background="#C9071029" Padding="22">
        <Grid>
          <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
          </Grid.RowDefinitions>
          <Grid Grid.Row="0">
            <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
            <StackPanel>
              <TextBlock x:Name="StageText" Text="Başlatılıyor..." FontSize="24" FontWeight="SemiBold"/>
              <TextBlock x:Name="DetailText" Text="Ders arşivi hazırlanıyor." Margin="0,5,0,0" Foreground="#9DABCA" FontSize="13"/>
            </StackPanel>
            <TextBlock x:Name="PercentText" Grid.Column="1" Text="0%" FontSize="28" FontWeight="Bold" VerticalAlignment="Center" Margin="20,0,0,0"/>
          </Grid>
          <ProgressBar x:Name="MainProgress" Grid.Row="1" Height="12" Margin="0,20,0,0" Minimum="0" Maximum="100" Value="0" Foreground="{StaticResource AuroraBrush}" Background="#18254C" BorderThickness="0"/>
          <TextBlock Grid.Row="2" x:Name="SubStatus" Text="Sistem kaynakları denetleniyor" Margin="0,14,0,0" Foreground="#76DFFF" FontSize="12"/>
        </Grid>
      </Border>
      <Border Grid.Column="1" Margin="16,0,0,0" CornerRadius="16" BorderBrush="#553B91" BorderThickness="1" Background="#C9151038" Padding="20">
        <StackPanel VerticalAlignment="Center">
          <TextBlock Text="LUNA ASİSTAN" Foreground="#C37BFF" FontSize="11" FontWeight="Bold"/>
          <TextBlock Text="Luna çalışıyor!" Margin="0,8,0,0" FontSize="21" FontWeight="SemiBold"/>
          <TextBlock Text="Kurulum ve başlangıç aşamalarını güvenli biçimde takip ediyor." Margin="0,8,0,0" TextWrapping="Wrap" Foreground="#A7B3D0" FontSize="12" LineHeight="18"/>
        </StackPanel>
      </Border>
    </Grid>

    <Border Grid.Row="2" Margin="28,8,28,12" CornerRadius="16" BorderBrush="#263A72" BorderThickness="1" Background="#E7050C20">
      <Grid>
        <Grid.RowDefinitions><RowDefinition Height="48"/><RowDefinition Height="*"/></Grid.RowDefinitions>
        <Grid Grid.Row="0" Background="#81101A39">
          <TextBlock Text="Başlangıç Günlükleri" Margin="18,0" VerticalAlignment="Center" FontSize="14" FontWeight="SemiBold"/>
          <TextBlock Text="Canlı" HorizontalAlignment="Right" Margin="0,0,18,0" VerticalAlignment="Center" Foreground="#52E1BC" FontSize="11"/>
        </Grid>
        <TextBox x:Name="LogBox" Grid.Row="1" Margin="14" Background="Transparent" Foreground="#B7C5E3" BorderThickness="0" IsReadOnly="True" TextWrapping="NoWrap" VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Auto" FontFamily="Consolas" FontSize="12"/>
      </Grid>
    </Border>

    <Grid Grid.Row="3" Margin="28,0,28,15">
      <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
      <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
        <Ellipse x:Name="StateDot" Width="9" Height="9" Fill="#42DFAD" Margin="0,0,9,0"/>
        <TextBlock x:Name="StateText" Text="Durum: Başlatılıyor" Foreground="#A9B6D2" VerticalAlignment="Center"/>
        <TextBlock Text="   |   Sürüm: 3.1.1   |   Yapım: Restless" Foreground="#64769B" VerticalAlignment="Center"/>
      </StackPanel>
      <StackPanel Grid.Column="1" Orientation="Horizontal">
        <Button x:Name="StopButton" Content="■  Durdur" Foreground="#FF8390" BorderBrush="#743449" Background="#281324" MinWidth="130" Margin="0,0,10,0"/>
        <Button x:Name="OptionsButton" Content="Logları aç" MinWidth="130"/>
      </StackPanel>
    </Grid>
  </Grid>
</Window>
"@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)
$window.FindName("HeroImage").Source = $heroBitmap

$stageText = $window.FindName("StageText")
$detailText = $window.FindName("DetailText")
$percentText = $window.FindName("PercentText")
$mainProgress = $window.FindName("MainProgress")
$subStatus = $window.FindName("SubStatus")
$logBox = $window.FindName("LogBox")
$stateText = $window.FindName("StateText")
$stateDot = $window.FindName("StateDot")
$stopButton = $window.FindName("StopButton")
$optionsButton = $window.FindName("OptionsButton")

$lastRaw = ""
$closingTimer = $null
$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(260)
$timer.Add_Tick({
    if (-not (Test-Path $StatusPath)) { return }
    try {
        $raw = [System.IO.File]::ReadAllText($StatusPath, [System.Text.Encoding]::UTF8)
        if (-not $raw -or $raw -eq $lastRaw) { return }
        $lastRaw = $raw
        $data = $raw | ConvertFrom-Json
        $percent = [Math]::Max(0, [Math]::Min(100, [int]$data.percent))
        $stageText.Text = [string]$data.title
        $detailText.Text = [string]$data.detail
        $percentText.Text = "$percent%"
        $mainProgress.Value = $percent
        $subStatus.Text = [string]$data.state
        $stateText.Text = "Durum: $($data.state)"
        if ($data.logs) {
            $logBox.Text = ($data.logs -join [Environment]::NewLine)
            $logBox.ScrollToEnd()
        }
        if ($data.error) {
            $stageText.Foreground = [Windows.Media.Brushes]::Salmon
            $stateDot.Fill = [Windows.Media.Brushes]::Tomato
            $stopButton.Content = "Kapat"
        }
        if ($data.done -and -not $closingTimer) {
            $stateDot.Fill = [Windows.Media.Brushes]::MediumSpringGreen
            $closingTimer = New-Object System.Windows.Threading.DispatcherTimer
            $closingTimer.Interval = [TimeSpan]::FromMilliseconds(1300)
            $closingTimer.Add_Tick({ $closingTimer.Stop(); $window.Close() })
            $closingTimer.Start()
        }
    } catch { }
})

$stopButton.Add_Click({
    if ($stopButton.Content -eq "Kapat") { $window.Close(); return }
    try { [System.IO.File]::WriteAllText($CancelPath, "1", [System.Text.Encoding]::ASCII) } catch { }
    $stopButton.IsEnabled = $false
    $stopButton.Content = "Durduruluyor..."
})

$optionsButton.Add_Click({
    try {
        if (Test-Path $LogPath) { Start-Process explorer.exe -ArgumentList "/select,`"$LogPath`"" }
        else { Start-Process explorer.exe -ArgumentList "`"$(Split-Path -Parent $LogPath)`"" }
    } catch { }
})

$window.Add_Loaded({ $timer.Start() })
$window.Add_Closed({ $timer.Stop(); if ($closingTimer) { $closingTimer.Stop() } })
[void]$window.ShowDialog()

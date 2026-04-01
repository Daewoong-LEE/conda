import SwiftUI

// MARK: - Design tokens

private enum DS {
    // Background — same saturated blue as the screenshot
    static let bg        = Color(red: 0.22, green: 0.50, blue: 0.76)
    static let surface   = Color.white.opacity(0.12)  // card / badge tint
    static let divider   = Color.white.opacity(0.25)

    // Accent colours
    static let green     = Color(red: 0.19, green: 0.82, blue: 0.35)   // progress, %, cache
    static let cyan      = Color(red: 0.35, green: 0.78, blue: 1.00)   // input
    static let pink      = Color(red: 1.00, green: 0.43, blue: 0.78)   // output
    static let blue      = Color(red: 0.25, green: 0.60, blue: 1.00)   // Refresh button

    // Typography
    static let labelFont  = Font.system(size: 13, weight: .semibold)
    static let valueFont  = Font.system(size: 13, weight: .regular, design: .monospaced)
    static let bigFont    = Font.system(size: 32, weight: .bold)
    static let medFont    = Font.system(size: 22, weight: .bold)
}

// MARK: - Root view

struct ContentView: View {
    @EnvironmentObject var monitor: TokenMonitor

    var body: some View {
        VStack(spacing: 0) {
            headerSection
            DS.divider.frame(height: 1)
            mainSection
            DS.divider.frame(height: 1)
            footerSection
        }
        .background(DS.bg)
        .foregroundColor(.white)
        .frame(width: 340)
    }
}

// MARK: - Header

private extension ContentView {
    var headerSection: some View {
        HStack(spacing: 10) {
            Image(systemName: "cloud.fill")
                .font(.system(size: 20))
                .foregroundColor(DS.cyan)

            Text("Claude Code")
                .font(.system(size: 17, weight: .bold))

            Spacer()

            Text("Max 5x")
                .font(.system(size: 13, weight: .medium))
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(DS.surface)
                .cornerRadius(8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

// MARK: - Main content

private extension ContentView {
    var mainSection: some View {
        VStack(alignment: .leading, spacing: 14) {

            // ── Token usage ──────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Token Usage")
                        .font(DS.labelFont)
                    Spacer()
                    Text("\(monitor.todayStats.totalTokens.formatted()) / \(monitor.sessionLimit.formatted())")
                        .font(.system(size: 13, weight: .regular))
                        .opacity(0.85)
                }

                TokenProgressBar(value: monitor.usagePercentage)

                Text("\(Int(monitor.usagePercentage * 100))% used")
                    .font(DS.bigFont)
                    .foregroundColor(DS.green)
            }

            // ── Session time ─────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 4) {
                Text("Session Time Remaining")
                    .font(DS.labelFont)

                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(monitor.timeRemainingString)
                        .font(DS.medFont)
                    Text(monitor.timeWindowLabel)
                        .font(.system(size: 14))
                        .opacity(0.75)
                }
            }

            // ── Three-column breakdown ───────────────────────────────────────
            HStack(spacing: 0) {
                statColumn(
                    title: "Input",
                    value: fmtTokens(monitor.todayStats.inputTokens),
                    color: DS.cyan
                )
                Spacer()
                statColumn(
                    title: "Output",
                    value: fmtTokens(monitor.todayStats.outputTokens),
                    color: DS.pink
                )
                Spacer()
                statColumn(
                    title: "Cache",
                    value: fmtTokens(monitor.todayStats.cacheCreationTokens
                                   + monitor.todayStats.cacheReadTokens),
                    color: DS.green
                )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 16)
    }

    func statColumn(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(DS.labelFont)
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .monospaced))
                .foregroundColor(color)
        }
    }
}

// MARK: - Footer

private extension ContentView {
    var footerSection: some View {
        HStack {
            Button {
                monitor.refresh()
            } label: {
                Text("Refresh")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(DS.blue)
            }
            .buttonStyle(.plain)
            .disabled(monitor.isRefreshing)

            Spacer()

            Button {
                NSApp.terminate(nil)
            } label: {
                Text("Quit")
                    .font(.system(size: 14, weight: .medium))
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

// MARK: - TokenProgressBar

struct TokenProgressBar: View {
    let value: Double   // 0.0 – 1.0

    private var barColor: Color {
        switch value {
        case ..<0.60: return DS.green
        case ..<0.85: return .orange
        default:      return .red
        }
    }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.white.opacity(0.20))
                    .frame(height: 8)
                Capsule()
                    .fill(barColor)
                    .frame(width: max(4, geo.size.width * value), height: 8)
                    .animation(.easeInOut(duration: 0.4), value: value)
            }
        }
        .frame(height: 8)
    }
}

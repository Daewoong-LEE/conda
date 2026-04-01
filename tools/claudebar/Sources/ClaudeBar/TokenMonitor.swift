import Foundation
import Combine

// MARK: - TokenMonitor

@MainActor
final class TokenMonitor: ObservableObject {

    // Published state that drives the SwiftUI view
    @Published var todayStats    = UsageStats()
    @Published var isRefreshing  = false

    // Claude Max 5x plan: 150 K tokens per 5-hour window
    let sessionLimit = 150_000
    let windowHours: Double = 5

    // Called after each refresh so AppDelegate can update the status-bar button
    var onUpdate: (() -> Void)?

    private let reader = ClaudeReader()

    // MARK: Computed

    var usagePercentage: Double {
        min(Double(todayStats.totalTokens) / Double(sessionLimit), 1.0)
    }

    var minutesRemaining: Int {
        guard let start = todayStats.firstTimestamp else { return 0 }
        let windowEnd = start.addingTimeInterval(windowHours * 3600)
        let remaining = windowEnd.timeIntervalSinceNow
        return remaining > 0 ? Int(remaining / 60) : 0
    }

    var timeRemainingString: String {
        let m = minutesRemaining
        guard m > 0 else { return "—" }
        return m >= 60 ? "\(m / 60)h \(m % 60)m" : "\(m)m"
    }

    var timeWindowLabel: String {
        "of \(Int(windowHours))h window"
    }

    // MARK: Actions

    func refresh() {
        guard !isRefreshing else { return }
        isRefreshing = true
        Task {
            let today = Calendar.current.startOfDay(for: Date())
            let stats = await reader.getStats(since: today)
            self.todayStats   = stats
            self.isRefreshing = false
            self.onUpdate?()
        }
    }
}

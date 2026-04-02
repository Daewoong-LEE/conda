import SwiftUI

@main
struct ClaudeBarApp: App {
    @StateObject private var vm = UsageViewModel()

    var body: some Scene {
        MenuBarExtra {
            PopoverView()
                .environmentObject(vm)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "cloud.fill")
                Text(vm.synced ? "\(vm.pct, specifier: "%.1f")%" : "…")
                    .foregroundColor(vm.pctColor)
            }
        }
        .menuBarExtraStyle(.window)
    }
}

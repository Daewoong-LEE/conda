import SwiftUI

struct PopoverView: View {
    @EnvironmentObject var vm: UsageViewModel

    var body: some View {
        if !vm.hasSessionKey {
            SetupView()
        } else {
            mainView
        }
    }

    private var mainView: some View {
        VStack(spacing: 0) {
            // ── Header ──
            HStack(spacing: 8) {
                Image(systemName: "cloud.fill").font(.title3)
                Text("Claude").font(.system(size: 17, weight: .bold))
                Spacer()
                Text(vm.synced ? "claude.ai" : "Local")
                    .font(.system(size: 12, weight: .medium))
                    .padding(.horizontal, 10).padding(.vertical, 3)
                    .background(Color.white.opacity(0.15))
                    .cornerRadius(9)
            }
            .padding(.horizontal, 14).padding(.vertical, 9)

            Divider().opacity(0.3)

            // ── Body ──
            VStack(spacing: 9) {
                // Token usage + progress bar
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("Token Usage").font(.system(size: 14, weight: .semibold))
                        Spacer()
                        Text("\(vm.tokensUsed) / 150k")
                            .font(.system(size: 13))
                            .foregroundColor(.white.opacity(0.6))
                    }
                    ProgressView(value: vm.pct, total: 100)
                        .tint(vm.pctColor)
                        .scaleEffect(x: 1, y: 1.4)
                    Text(String(format: "%.1f%% used", vm.pct))
                        .font(.system(size: 36, weight: .heavy))
                        .foregroundColor(vm.pctColor)
                }

                // Session time remaining
                VStack(alignment: .leading, spacing: 3) {
                    Text("Session Time Remaining")
                        .font(.system(size: 14, weight: .semibold))
                    HStack(alignment: .lastTextBaseline, spacing: 6) {
                        Text(vm.timeString)
                            .font(.system(size: 26, weight: .bold))
                        Text("of 5h window")
                            .font(.system(size: 14))
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            .foregroundColor(.white)

            Divider().opacity(0.3)

            // ── Footer ──
            HStack {
                Button(action: { Task { await vm.refresh() } }) {
                    if vm.isLoading {
                        ProgressView().scaleEffect(0.7)
                    } else {
                        Text("Refresh")
                    }
                }
                .foregroundColor(.blue)
                Spacer()
                Button("Sign Out") { vm.signOut() }
                    .foregroundColor(.secondary)
                Button("Quit") { NSApplication.shared.terminate(nil) }
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 14).padding(.vertical, 6)
        }
        .frame(width: 300)
        .background(Color(NSColor(red: 0.22, green: 0.22, blue: 0.22, alpha: 1)))
        .preferredColorScheme(.dark)
    }
}

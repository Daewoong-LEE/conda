import SwiftUI

struct SetupView: View {
    @EnvironmentObject var vm: UsageViewModel
    @State private var input = ""
    @State private var showGuide = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "cloud.fill").foregroundColor(.blue)
                Text("ClaudeBar 설정").font(.headline)
            }

            Text("claude.ai 세션 키를 입력하면\n실시간 사용량이 표시됩니다.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            if showGuide {
                VStack(alignment: .leading, spacing: 4) {
                    Text("세션 키 찾는 법:").font(.caption).bold()
                    Text("1. Chrome에서 claude.ai 열기")
                    Text("2. F12 → Application → Cookies")
                    Text("3. sessionKey 값 복사")
                }
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(8)
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(6)
            }

            SecureField("sk-ant-sid02-...", text: $input)
                .textFieldStyle(.roundedBorder)

            HStack {
                Button(showGuide ? "닫기" : "세션 키 찾는 법") {
                    showGuide.toggle()
                }
                .foregroundColor(.blue)
                Spacer()
                Button("저장") {
                    let key = input.trimmingCharacters(in: .whitespaces)
                    if !key.isEmpty { vm.saveSessionKey(key) }
                }
                .buttonStyle(.borderedProminent)
                .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty)
            }

            Divider()
            Button("Quit") { NSApplication.shared.terminate(nil) }
                .foregroundColor(.secondary)
        }
        .padding(16)
        .frame(width: 300)
    }
}

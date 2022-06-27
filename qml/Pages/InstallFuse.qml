import QtQuick 2.7
import Ubuntu.Components 1.3
import Ubuntu.Components.Popups 1.3
//import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3

Page {
    anchors.fill: parent

    header: PageHeader {
        id: header
        title: gocryptfs.isLoading ? i18n.tr('Installing...') : i18n.tr('Attention!')
    }

    // FIXME: Some of elements in this layout rely on hack calculations that work on certain window sizes
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: header.height

        id: warningColumn
        spacing: units.gu(4)

        Item { Layout.fillHeight: true }

        Icon {
            id: warnIcon
            Layout.preferredWidth: (parent.width / 6) + units.gu(4)
            Layout.preferredHeight: Layout.preferredWidth
    
            Layout.maximumWidth: units.gu(15)

            Layout.alignment: Qt.AlignCenter

            name: "security-alert"
        }

        Label {
            id: warnText
            Layout.fillWidth: true

            text: i18n.tr("This app requires installing additional system components (Fuse).\nThis may fail on some devices, due to the RootFS size.\nThe download will take around 25 kB.\nKeep in mind that this message will reappear after a system update.")

            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            lineHeight: 1.8

            Layout.leftMargin: units.gu(4)
            Layout.rightMargin: units.gu(4)
        }

        Button {
            id: acceptButton
            Layout.alignment: Qt.AlignCenter
            Layout.preferredWidth: (parent.width / 5) + units.gu(2)

            text: i18n.tr("Continue")
            color: theme.palette.normal.positive

            onClicked: {
                var popup = PopupUtils.open(passwordPopup)
                popup.accepted.connect(function(password) {

                    gocryptfs.isLoading = true;
                    gocryptfs.call('gocryptfs.install_fuse', [password], function() {
                        gocryptfs.isLoading = false;
                        pStack.pop()
                        pStack.push(Qt.resolvedUrl("./Pages/VaultList.qml"));
                    });
                })
            }
        }

        Item { Layout.fillHeight: true }
    }

    Component {
        id: passwordPopup

        Dialog {
            id: passwordDialog
            title: i18n.tr("Enter password")
            text: i18n.tr("Your password is required for this action.")

            signal accepted(string password)
            signal rejected()

            TextField {
                id: passwordTextField
                placeholderText: i18n.tr("Password")
                echoMode: TextInput.Password
                focus: true
            }

            Button {
                text: i18n.tr("OK")
                color: theme.palette.normal.positive

                onClicked: {
                    passwordDialog.accepted(passwordTextField.text)
                    PopupUtils.close(passwordDialog)
                }
            }

            Button {
                text: i18n.tr("Cancel")
                color: theme.palette.normal.negative

                onClicked: {
                    passwordDialog.rejected();
                    PopupUtils.close(passwordDialog)
                }
            }
        }
    }
}